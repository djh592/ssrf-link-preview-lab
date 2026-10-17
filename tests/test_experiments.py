import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from ssrf_link_preview_lab.experiments.event_models import (
    ExternalRedirect,
    InternalReportAccess,
    PreviewFetchCompleted,
    TrialEvent,
)
from ssrf_link_preview_lab.experiments.event_parser import parse_trial_events
from ssrf_link_preview_lab.experiments.redirect_baseline import (
    REDIRECT_BASELINE_SPEC,
    evaluate_redirect_baseline,
)
from ssrf_link_preview_lab.experiments.results import save_trial_run
from ssrf_link_preview_lab.experiments.runner import execute_trial
from ssrf_link_preview_lab.experiments.terminal import render_trial_run
from ssrf_link_preview_lab.experiments.trial_models import (
    EvidenceCheck,
    ExecutionStatus,
    PreviewObservation,
    SecurityOutcome,
    TrialResult,
    TrialRun,
    VerificationStatus,
)
from ssrf_link_preview_lab.lab.constants import INTERNAL_REPORT_MARKER

_TRIAL_ID = UUID("297cd742-81b3-42d5-b06c-893a3901739a")
_TIMESTAMP = datetime(2026, 10, 15, 16, 11, 52, 886000, tzinfo=UTC)


def test_parses_only_typed_events_for_the_requested_trial() -> None:
    other_trial_id = UUID("6518730c-c8e5-440a-94ff-85603deac87c")
    matching_event = {
        "timestamp": "2026-10-15T16:11:52.886+00:00",
        "event": "external_redirect",
        "trial_id": str(_TRIAL_ID),
        "location": "http://internal-report:8080/report",
    }
    other_event = matching_event | {"trial_id": str(other_trial_id)}
    malformed_event = matching_event | {"location": 42}
    output = "\n".join(
        (
            "INFO: server started",
            json.dumps(other_event),
            json.dumps(malformed_event),
            json.dumps(matching_event),
        )
    )

    events = parse_trial_events("external-page", output, trial_id=_TRIAL_ID)

    assert events == (
        TrialEvent(
            timestamp=_TIMESTAMP,
            service="external-page",
            trial_id=_TRIAL_ID,
            details=ExternalRedirect("http://internal-report:8080/report"),
        ),
    )


def test_parses_preview_trace_into_fetch_models() -> None:
    record = {
        "timestamp": "2026-10-15T16:11:52.886+00:00",
        "event": "preview_fetch_completed",
        "trial_id": str(_TRIAL_ID),
        "requested_url": REDIRECT_BASELINE_SPEC.target_url,
        "final_url": "http://internal-report:8080/report",
        "trace": {
            "hops": [
                {
                    "sequence": 0,
                    "url": REDIRECT_BASELINE_SPEC.target_url,
                    "status_code": 302,
                    "peer_ip": "172.20.0.2",
                    "location": "http://internal-report:8080/report",
                    "redirect_url": "http://internal-report:8080/report",
                    "observed_at": 123.25,
                }
            ],
            "address_decisions": [],
        },
    }

    events = parse_trial_events("preview", json.dumps(record), trial_id=_TRIAL_ID)

    assert len(events) == 1
    assert isinstance(events[0].details, PreviewFetchCompleted)
    assert events[0].details.trace.hops[0].status_code == 302
    assert events[0].details.trace.hops[0].observed_at == 123.25


def test_evaluates_and_renders_vulnerable_baseline_without_ambiguous_pass() -> None:
    preview = _internal_preview()
    event = TrialEvent(
        timestamp=_TIMESTAMP,
        service="internal-report",
        trial_id=_TRIAL_ID,
        details=InternalReportAccess(
            source_trial_id=_TRIAL_ID,
            trial_ids_match=True,
        ),
    )

    result = evaluate_redirect_baseline(
        preview=preview,
        direct_external_access_blocked=True,
        events=(event,),
    )
    run = TrialRun(
        spec=REDIRECT_BASELINE_SPEC,
        status=ExecutionStatus.COMPLETED,
        started_at=_TIMESTAMP,
        duration_seconds=1.25,
        result=result,
    )
    rendered = render_trial_run(run)

    assert result.verification_status is VerificationStatus.PASSED
    assert result.observed_security_outcome is SecurityOutcome.VULNERABLE
    assert all(check.satisfied for check in result.evidence)
    assert "Experiment verification  PASSED" in rendered
    assert "Observed security outcome  VULNERABLE" in rendered
    assert "Internal request                     OBSERVED" in rendered


def test_missing_attack_evidence_is_failed_and_inconclusive() -> None:
    preview = PreviewObservation(
        trial_id=_TRIAL_ID,
        requested_url=REDIRECT_BASELINE_SPEC.target_url,
        final_url="http://external-page:8080/page",
        title="External page",
        description="No internal marker",
    )

    result = evaluate_redirect_baseline(
        preview=preview,
        direct_external_access_blocked=True,
        events=(),
    )

    assert result.verification_status is VerificationStatus.FAILED
    assert result.observed_security_outcome is SecurityOutcome.INCONCLUSIVE
    assert [check.satisfied for check in result.evidence] == [True, False, False]


def test_generic_renderer_supports_a_protected_outcome() -> None:
    result = TrialResult(
        spec=REDIRECT_BASELINE_SPEC,
        trial_id=_TRIAL_ID,
        verification_status=VerificationStatus.PASSED,
        observed_security_outcome=SecurityOutcome.PROTECTED,
        evidence=(
            EvidenceCheck(
                key="internal_access_blocked",
                label="Internal access",
                satisfied=True,
                satisfied_label="BLOCKED",
                unsatisfied_label="OBSERVED",
            ),
        ),
        preview=_internal_preview(),
        events=(),
    )
    run = TrialRun(
        spec=REDIRECT_BASELINE_SPEC,
        status=ExecutionStatus.COMPLETED,
        started_at=_TIMESTAMP,
        duration_seconds=0.5,
        result=result,
    )

    rendered = render_trial_run(run)

    assert "Internal access                      BLOCKED" in rendered
    assert "Observed security outcome  PROTECTED" in rendered


def test_execution_errors_are_structured_and_persisted(tmp_path: Path) -> None:
    def fail() -> TrialResult:
        raise RuntimeError("controlled setup failure")

    run = execute_trial(REDIRECT_BASELINE_SPEC, fail)
    result_path = save_trial_run(run, tmp_path / "results")
    persisted = json.loads(result_path.read_text())

    assert run.status is ExecutionStatus.ERROR
    assert run.error is not None
    assert run.error.error_type == "RuntimeError"
    assert run.duration_seconds >= 0
    assert persisted["execution"]["status"] == "error"
    assert persisted["error"] == {
        "message": "controlled setup failure",
        "type": "RuntimeError",
    }
    assert list((tmp_path / "results").glob("*.tmp")) == []


def _internal_preview() -> PreviewObservation:
    return PreviewObservation(
        trial_id=_TRIAL_ID,
        requested_url=REDIRECT_BASELINE_SPEC.target_url,
        final_url=f"http://internal-report:8080/report?source_trial_id={_TRIAL_ID}",
        title="Internal report",
        description=f"{INTERNAL_REPORT_MARKER}; trial_id={_TRIAL_ID}",
    )
