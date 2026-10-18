import json
from collections.abc import Callable
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from ssrf_link_preview_lab.experiments.compose import ComposeProject
from ssrf_link_preview_lab.experiments.event_models import (
    InternalReportAccess,
    TrialEvent,
)
from ssrf_link_preview_lab.experiments.event_parser import parse_trial_events
from ssrf_link_preview_lab.experiments.trial_models import (
    EvidenceCheck,
    PreviewObservation,
    SecurityOutcome,
    TrialResult,
    TrialSpec,
    VerificationStatus,
)
from ssrf_link_preview_lab.lab.constants import INTERNAL_REPORT_MARKER

REDIRECT_BASELINE_SPEC = TrialSpec(
    scenario="redirect-to-internal-service",
    policy="unfiltered",
    target_url="http://external-page:8080/redirect/internal",
    expected_security_outcome=SecurityOutcome.VULNERABLE,
)

_EXPECTED_SERVICES = {"external-page", "internal-report", "preview"}
_INTERNAL_REPORT_URL = "http://internal-report:8080/report"
_LAB_CLIENT_MODULE = "ssrf_link_preview_lab.lab.client"

ProgressReporter = Callable[[str], None]


def run_redirect_baseline(
    project: ComposeProject,
    *,
    report_progress: ProgressReporter | None = None,
) -> TrialResult:
    _report(report_progress, "Checking that all lab services are running")
    project.require_running_services(_EXPECTED_SERVICES)

    _report(report_progress, "Checking external-to-internal network isolation")
    direct_access_blocked = _external_access_is_blocked(project)

    _report(report_progress, "Submitting the controlled redirect trial")
    preview = _request_preview(project)

    _report(report_progress, "Collecting trial-scoped service events")
    events = _collect_events(project, preview.trial_id)

    _report(report_progress, "Evaluating the observed security outcome")
    return evaluate_redirect_baseline(
        preview=preview,
        direct_external_access_blocked=direct_access_blocked,
        events=events,
    )


def evaluate_redirect_baseline(
    *,
    preview: PreviewObservation,
    direct_external_access_blocked: bool,
    events: tuple[TrialEvent, ...],
) -> TrialResult:
    internal_access_observed = any(
        isinstance(event.details, InternalReportAccess)
        and event.details.source_trial_id == preview.trial_id
        and event.details.trial_ids_match
        for event in events
    )
    final_url = urlsplit(preview.final_url)
    marker_disclosed = (
        preview.description is not None
        and INTERNAL_REPORT_MARKER in preview.description
        and final_url.hostname == "internal-report"
        and final_url.path == "/report"
        and parse_qs(final_url.query).get("source_trial_id") == [str(preview.trial_id)]
    )
    evidence = (
        EvidenceCheck(
            key="external_to_internal_direct_access_blocked",
            label="External -> internal direct access",
            satisfied=direct_external_access_blocked,
            satisfied_label="BLOCKED",
            unsatisfied_label="REACHABLE",
        ),
        EvidenceCheck(
            key="internal_request_observed",
            label="Internal request",
            satisfied=internal_access_observed,
            satisfied_label="OBSERVED",
            unsatisfied_label="NOT OBSERVED",
        ),
        EvidenceCheck(
            key="internal_marker_disclosed",
            label="Internal marker disclosure",
            satisfied=marker_disclosed,
            satisfied_label="OBSERVED",
            unsatisfied_label="NOT OBSERVED",
        ),
    )
    observed_outcome = (
        SecurityOutcome.VULNERABLE
        if internal_access_observed or marker_disclosed
        else SecurityOutcome.INCONCLUSIVE
    )

    return TrialResult(
        spec=REDIRECT_BASELINE_SPEC,
        trial_id=preview.trial_id,
        verification_status=(
            VerificationStatus.PASSED
            if all(check.satisfied for check in evidence)
            else VerificationStatus.FAILED
        ),
        observed_security_outcome=observed_outcome,
        evidence=evidence,
        preview=preview,
        events=tuple(sorted(events, key=lambda event: event.timestamp)),
    )


def _external_access_is_blocked(project: ComposeProject) -> bool:
    result = project.exec_module(
        "external-page",
        _LAB_CLIENT_MODULE,
        "probe",
        _INTERNAL_REPORT_URL,
        "--timeout",
        "2",
    )
    payload = _json_object(result.stdout, description="Network isolation probe")
    reachable = payload.get("reachable")
    if not isinstance(reachable, bool):
        raise TypeError("Network isolation probe did not return a boolean 'reachable'")
    return not reachable


def _request_preview(project: ComposeProject) -> PreviewObservation:
    result = project.exec_module(
        "preview",
        _LAB_CLIENT_MODULE,
        "preview",
        REDIRECT_BASELINE_SPEC.target_url,
    )
    response = _json_object(result.stdout, description="Preview client")
    if response.get("ok") is not True:
        raise RuntimeError(
            "Preview request failed: "
            f"status={response.get('status_code')!r}, error={response.get('error')!r}"
        )
    payload = response.get("body")
    if not isinstance(payload, dict):
        raise TypeError("Preview endpoint returned a non-object response")

    trial_id = UUID(_required_string(payload, "trial_id"))
    return PreviewObservation(
        trial_id=trial_id,
        requested_url=_required_string(payload, "requested_url"),
        final_url=_required_string(payload, "final_url"),
        title=_optional_string(payload, "title"),
        description=_optional_string(payload, "description"),
    )


def _collect_events(
    project: ComposeProject,
    trial_id: UUID,
) -> tuple[TrialEvent, ...]:
    events: list[TrialEvent] = []
    for service in sorted(_EXPECTED_SERVICES):
        events.extend(
            parse_trial_events(service, project.logs(service), trial_id=trial_id)
        )
    return tuple(events)


def _json_object(output: str, *, description: str) -> dict[object, object]:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as error:
        raise ValueError(f"{description} returned invalid JSON") from error
    if not isinstance(payload, dict):
        raise TypeError(f"{description} returned a non-object response")
    return payload


def _required_string(payload: dict[object, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str):
        raise TypeError(f"Preview response field {field!r} must be a string")
    return value


def _optional_string(payload: dict[object, object], field: str) -> str | None:
    value = payload.get(field)
    if value is not None and not isinstance(value, str):
        raise TypeError(f"Preview response field {field!r} must be a string or null")
    return value


def _report(reporter: ProgressReporter | None, message: str) -> None:
    if reporter is not None:
        reporter(message)
