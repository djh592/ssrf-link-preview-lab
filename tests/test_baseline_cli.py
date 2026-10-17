import json
from pathlib import Path
from uuid import UUID

import pytest
from pytest import CaptureFixture, MonkeyPatch

from ssrf_link_preview_lab.experiments import cli
from ssrf_link_preview_lab.experiments.redirect_baseline import REDIRECT_BASELINE_SPEC
from ssrf_link_preview_lab.experiments.trial_models import (
    PreviewObservation,
    SecurityOutcome,
    TrialResult,
    VerificationStatus,
)


@pytest.mark.parametrize("output_format", ["text", "json"])
@pytest.mark.parametrize(
    ("verification_status", "expected_exit_code"),
    [(VerificationStatus.PASSED, 0), (VerificationStatus.FAILED, 1)],
)
def test_baseline_cli_uses_one_trial_for_both_formats(
    output_format: str,
    verification_status: VerificationStatus,
    expected_exit_code: int,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    tmp_path: Path,
) -> None:
    trial_id = UUID(int=1)
    result = TrialResult(
        spec=REDIRECT_BASELINE_SPEC,
        trial_id=trial_id,
        verification_status=verification_status,
        observed_security_outcome=SecurityOutcome.VULNERABLE,
        evidence=(),
        preview=PreviewObservation(
            trial_id=trial_id,
            requested_url=REDIRECT_BASELINE_SPEC.target_url,
            final_url="http://internal-report:8080/report",
            title="Internal report",
            description="Synthetic report",
        ),
        events=(),
    )

    def fake_trial(root: Path, reporter: object) -> TrialResult:
        del root, reporter
        return result

    monkeypatch.setattr(cli, "_run_managed_trial", fake_trial)

    exit_code = cli.run_redirect_baseline_cli(tmp_path, ["--format", output_format])
    output = capsys.readouterr()
    records = list((tmp_path / "results").glob("*.json"))

    assert exit_code == expected_exit_code
    assert len(records) == 1
    assert json.loads(records[0].read_text())["result"]["trial_id"] == str(trial_id)
    if output_format == "json":
        assert json.loads(output.out)["result"]["trial_id"] == str(trial_id)
        assert "Raw result saved" in output.err
    else:
        assert f"Experiment verification  {verification_status.upper()}" in output.out
        assert "Raw result saved" in output.out
