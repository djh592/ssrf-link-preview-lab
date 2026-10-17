import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from ssrf_link_preview_lab.experiments.compose import (
    ComposeProject,
    ComposeProjectInUseError,
)


def test_compose_commands_use_an_explicit_project_and_instance(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    observed: dict[str, object] = {}

    def fake_run(
        command: Sequence[str], **options: object
    ) -> subprocess.CompletedProcess[str]:
        observed["command"] = tuple(command)
        observed["options"] = options
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv("COMPOSE_FILE", "/tmp/unrelated-compose.yaml")
    project = ComposeProject(tmp_path, "alice-redirect", command_timeout_seconds=12)

    project.validate()

    assert observed["command"] == (
        "docker",
        "compose",
        "--file",
        str(tmp_path / "compose.yaml"),
        "--project-name",
        "ssrf-link-preview-alice-redirect",
        "config",
        "--quiet",
    )
    options = observed["options"]
    assert isinstance(options, dict)
    assert options["cwd"] == tmp_path
    assert options["timeout"] == 12
    environment = options["env"]
    assert isinstance(environment, dict)
    assert environment["SSRF_LAB_INSTANCE"] == "alice-redirect"
    assert "COMPOSE_FILE" not in environment


def test_browser_overlay_uses_the_same_project_and_limits_parallelism(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    observed: dict[str, object] = {}

    def fake_run(
        command: Sequence[str], **options: object
    ) -> subprocess.CompletedProcess[str]:
        observed["command"] = tuple(command)
        observed["environment"] = options["env"]
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    project = ComposeProject(tmp_path, "alice-browser", overlays=("compose.demo.yaml",))
    project.validate()

    assert observed["command"] == (
        "docker",
        "compose",
        "--file",
        str(tmp_path / "compose.yaml"),
        "--file",
        str(tmp_path / "compose.demo.yaml"),
        "--project-name",
        "ssrf-link-preview-alice-browser",
        "config",
        "--quiet",
    )
    environment = observed["environment"]
    assert isinstance(environment, dict)
    assert environment["COMPOSE_PARALLEL_LIMIT"] == "1"


@pytest.mark.parametrize(
    "instance", ["", "Alice", "-alice", "alice/redirect", "a" * 49]
)
def test_rejects_unsafe_compose_instance_names(instance: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        ComposeProject(tmp_path, instance)


def test_managed_services_clean_up_after_trial_failure(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    commands: list[tuple[str, ...]] = []

    def fake_run(
        command: Sequence[str], **options: object
    ) -> subprocess.CompletedProcess[str]:
        del options
        command_tuple = tuple(command)
        commands.append(command_tuple)
        stdout = "  \n" if "ps" in command_tuple else ""
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    project = ComposeProject(tmp_path, "alice-redirect")

    with (
        pytest.raises(RuntimeError, match="controlled failure"),
        project.running_services(),
    ):
        raise RuntimeError("controlled failure")

    assert _compose_arguments(commands) == [
        ("config", "--quiet"),
        ("ps", "--all", "--services"),
        ("up", "--detach", "--wait", "--no-build"),
        ("down", "--remove-orphans"),
    ]


def test_managed_services_refuse_to_take_over_existing_containers(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    commands: list[tuple[str, ...]] = []

    def fake_run(
        command: Sequence[str], **options: object
    ) -> subprocess.CompletedProcess[str]:
        del options
        command_tuple = tuple(command)
        commands.append(command_tuple)
        stdout = "preview\n" if "ps" in command_tuple else ""
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    project = ComposeProject(tmp_path, "alice-redirect")

    with (
        pytest.raises(ComposeProjectInUseError, match="already has containers"),
        project.running_services(),
    ):
        pass

    assert _compose_arguments(commands) == [
        ("config", "--quiet"),
        ("ps", "--all", "--services"),
    ]


def test_cleanup_failure_does_not_mask_the_trial_failure(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_run(
        command: Sequence[str], **options: object
    ) -> subprocess.CompletedProcess[str]:
        del options
        if tuple(command[-2:]) == ("down", "--remove-orphans"):
            return subprocess.CompletedProcess(
                command, 1, stdout="", stderr="controlled cleanup failure"
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    project = ComposeProject(tmp_path, "alice-redirect")

    with (
        pytest.raises(RuntimeError, match="controlled trial failure") as caught,
        project.running_services(),
    ):
        raise RuntimeError("controlled trial failure")

    assert caught.value.__notes__ == [
        (
            "Cleanup also failed: docker compose --file "
            f"{tmp_path / 'compose.yaml'} --project-name "
            "ssrf-link-preview-alice-redirect down --remove-orphans failed with "
            "exit code 1: controlled cleanup failure"
        )
    ]


def _compose_arguments(commands: list[tuple[str, ...]]) -> list[tuple[str, ...]]:
    return [command[6:] for command in commands]
