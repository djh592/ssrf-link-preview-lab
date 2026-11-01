import re
import subprocess
from collections.abc import Collection, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from os import environ
from pathlib import Path

_INSTANCE_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}\Z")
_DEFAULT_COMMAND_TIMEOUT_SECONDS = 60.0


class ComposeCommandError(RuntimeError):
    def __init__(
        self,
        command: tuple[str, ...],
        result: subprocess.CompletedProcess[str],
    ) -> None:
        self.command = command
        self.returncode = result.returncode
        detail = result.stderr.strip() or result.stdout.strip() or "no error output"
        super().__init__(
            f"{' '.join(command)} failed with exit code {result.returncode}: {detail}"
        )


class ComposeCommandTimeoutError(RuntimeError):
    def __init__(self, command: tuple[str, ...], timeout_seconds: float) -> None:
        self.command = command
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"{' '.join(command)} exceeded the {timeout_seconds:g}-second timeout"
        )


class ComposeProjectInUseError(RuntimeError):
    def __init__(self, project_name: str, services: Collection[str]) -> None:
        service_list = ", ".join(sorted(services))
        super().__init__(
            f"Compose project {project_name!r} already has containers: {service_list}. "
            "Choose another SSRF_LAB_INSTANCE or stop that project explicitly."
        )


@dataclass(frozen=True, slots=True)
class ComposeProject:
    """Run Compose commands against one instance-named project.

    Commands use an explicit Compose file list and project name. Runtime
    commands also remove inherited Compose options and limit parallelism.
    """

    root: Path
    instance: str
    command_timeout_seconds: float = _DEFAULT_COMMAND_TIMEOUT_SECONDS
    overlays: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if _INSTANCE_PATTERN.fullmatch(self.instance) is None:
            raise ValueError(
                "SSRF_LAB_INSTANCE must start with a lowercase letter or digit, "
                "contain only lowercase letters, digits, hyphens, or underscores, "
                "and be at most 48 characters"
            )
        if self.command_timeout_seconds <= 0:
            raise ValueError("command_timeout_seconds must be positive")

    @classmethod
    def from_environment(cls, root: Path) -> "ComposeProject":
        instance = environ.get("SSRF_LAB_INSTANCE")
        if instance is None:
            raise RuntimeError(
                "SSRF_LAB_INSTANCE must identify this user's lab resources"
            )
        return cls(root=root, instance=instance)

    @property
    def project_name(self) -> str:
        return f"ssrf-link-preview-{self.instance}"

    def run(
        self,
        *arguments: str,
        check: bool = True,
        timeout_seconds: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run a scoped Compose command with a bounded execution time."""
        command = self._command(*arguments)
        timeout = (
            self.command_timeout_seconds if timeout_seconds is None else timeout_seconds
        )
        if timeout <= 0:
            raise ValueError("timeout_seconds must be positive")
        environment = {
            name: value
            for name, value in environ.items()
            if not name.startswith("COMPOSE_")
        }
        environment["SSRF_LAB_INSTANCE"] = self.instance
        environment["COMPOSE_PARALLEL_LIMIT"] = "1"
        try:
            result = subprocess.run(
                command,
                cwd=self.root,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise ComposeCommandTimeoutError(command, timeout) from error
        if check and result.returncode != 0:
            raise ComposeCommandError(command, result)
        return result

    def validate(self) -> None:
        self.run("config", "--quiet")

    def services(self, *, include_stopped: bool = False) -> frozenset[str]:
        arguments = ["ps"]
        if include_stopped:
            arguments.append("--all")
        arguments.append("--services")
        return frozenset(
            service
            for line in self.run(*arguments).stdout.splitlines()
            if (service := line.strip())
        )

    def require_running_services(self, expected: Collection[str]) -> None:
        missing = set(expected) - self.services()
        if missing:
            raise RuntimeError(
                f"Lab services are not running: {', '.join(sorted(missing))}"
            )

    def exec_module(
        self,
        service: str,
        module: str,
        *arguments: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        return self.run(
            "exec",
            "-T",
            service,
            "python",
            "-m",
            module,
            *arguments,
            check=check,
        )

    def logs(self, service: str, *, since: str | None = None) -> str:
        arguments = ["logs", "--no-color", "--no-log-prefix"]
        if since is not None:
            arguments.extend(("--since", since))
        return self.run(*arguments, service).stdout

    def _command(self, *arguments: str) -> tuple[str, ...]:
        command = (
            "docker",
            "compose",
            "--file",
            str(self.root / "compose.yaml"),
            *(
                part
                for overlay in self.overlays
                for part in ("--file", str(self.root / overlay))
            ),
            "--project-name",
            self.project_name,
            *arguments,
        )
        return command

    @contextmanager
    def running_services(self) -> Generator[None]:
        """Start unused lab resources and tear down this project on exit.

        Existing containers with the same project name are left untouched.
        Cleanup failures are attached to an active error instead of replacing
        it; callers must still inspect that secondary failure.
        """
        self.validate()
        existing = self.services(include_stopped=True)
        if existing:
            raise ComposeProjectInUseError(self.project_name, existing)

        active_error: BaseException | None = None
        try:
            self.run("up", "--detach", "--wait", "--no-build")
            yield
        except BaseException as error:
            active_error = error
            raise
        finally:
            try:
                cleanup = self.run("down", "--remove-orphans", check=False)
                if cleanup.returncode != 0:
                    raise ComposeCommandError(
                        self._command("down", "--remove-orphans"), cleanup
                    )
            except Exception as cleanup_error:
                if active_error is None:
                    raise
                active_error.add_note(f"Cleanup also failed: {cleanup_error}")
