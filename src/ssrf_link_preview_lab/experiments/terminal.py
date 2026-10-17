"""Render automated trial evidence for terminal readers."""

from datetime import UTC

from ssrf_link_preview_lab.experiments.event_models import (
    ExternalPageAccess,
    ExternalRedirect,
    InternalReportAccess,
    PreviewFetchCompleted,
    PreviewFetchFailed,
    TrialEvent,
)
from ssrf_link_preview_lab.experiments.trial_models import TrialRun


def render_trial_run(run: TrialRun) -> str:
    lines = [
        "SSRF Link Preview Lab",
        "=" * 72,
        f"Scenario             {run.spec.scenario}",
        f"Policy               {run.spec.policy}",
        f"Execution            {run.status.value.upper()}",
        f"Duration             {run.duration_seconds:.3f} seconds",
    ]
    if run.error is not None:
        lines.extend(
            [
                "",
                "Execution error",
                "---------------",
                f"Type                  {run.error.error_type}",
                f"Message               {run.error.message}",
                "",
                "Result",
                "------",
                "Experiment verification  NOT RUN",
                (
                    "Expected security outcome "
                    f" {run.spec.expected_security_outcome.value.upper()}"
                ),
                "Observed security outcome  INCONCLUSIVE",
            ]
        )
        return "\n".join(lines)

    result = run.result
    if result is None:
        raise ValueError("A completed trial run must contain a result")

    lines.extend(
        [
            f"Trial ID             {result.trial_id}",
            "",
            "Observed request path",
            "---------------------",
            f"Requested URL        {result.preview.requested_url}",
            f"Final URL            {result.preview.final_url}",
            "",
            "Trial timeline (UTC)",
            "--------------------",
        ]
    )
    if result.events:
        for event in result.events:
            lines.extend(_render_event(event))
    else:
        lines.append("No trial-scoped service events were recorded.")

    lines.extend(("", "Evidence", "--------"))
    lines.extend(
        f"{check.label:<36} {check.observed_label}" for check in result.evidence
    )
    lines.extend(
        [
            "",
            "Result",
            "------",
            f"Experiment verification  {result.verification_status.value.upper()}",
            (
                "Expected security outcome "
                f" {run.spec.expected_security_outcome.value.upper()}"
            ),
            (
                "Observed security outcome "
                f" {result.observed_security_outcome.value.upper()}"
            ),
        ]
    )
    return "\n".join(lines)


def _render_event(event: TrialEvent) -> list[str]:
    timestamp = event.timestamp.astimezone(UTC).strftime("%H:%M:%S.%f")[:-3] + "Z"
    details = event.details
    if isinstance(details, ExternalRedirect):
        summary = "External service issued redirect"
        detail = details.location
    elif isinstance(details, InternalReportAccess):
        summary = "Internal report received request"
        detail = f"trial IDs match: {details.trial_ids_match}"
    elif isinstance(details, ExternalPageAccess):
        summary = "External page received request"
        detail = None
    elif isinstance(details, PreviewFetchCompleted):
        summary = "Preview fetch completed"
        detail = f"{len(details.trace.hops)} HTTP hop(s)"
    elif isinstance(details, PreviewFetchFailed):
        summary = "Preview fetch failed"
        detail = f"{details.error_type}: {details.message}"

    lines = [f"{timestamp}  {event.service:<16} {summary}"]
    if detail is not None:
        lines.append(f"              {'':16} {detail}")
    return lines
