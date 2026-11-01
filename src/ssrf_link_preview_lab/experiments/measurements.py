"""Collect independent service evidence for one offline preview attempt."""

import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import isfinite
from typing import Protocol
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from ssrf_link_preview_lab.experiments.event_models import (
    InternalReportAccess,
    TrialEvent,
)
from ssrf_link_preview_lab.experiments.event_parser import (
    parse_fetch_trace,
    parse_trial_events,
)
from ssrf_link_preview_lab.experiments.scenarios import (
    Scenario,
    ScenarioCase,
    ScenarioKind,
)
from ssrf_link_preview_lab.fetching.models import ConnectionAttempt, FetchTrace
from ssrf_link_preview_lab.fetching.strategies import Defense
from ssrf_link_preview_lab.lab.constants import INTERNAL_REPORT_MARKER


class MeasurementProject(Protocol):
    def exec_module(
        self, service: str, module: str, *arguments: str, check: bool = True
    ) -> subprocess.CompletedProcess[str]: ...

    def logs(self, service: str, *, since: str | None = None) -> str: ...


@dataclass(frozen=True, slots=True)
class Measurement:
    scenario: Scenario
    defense: Defense
    repetition: int
    trial_id: UUID
    kind: ScenarioKind
    target_url: str
    preview: dict[str, object] | None
    internal_access: bool | None
    marker_disclosed: bool | None
    normal_success: bool | None
    duration_seconds: float | None
    error: str | None = None
    service_events: tuple[TrialEvent, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "scenario": self.scenario,
            "defense": self.defense,
            "repetition": self.repetition,
            "trial_id": str(self.trial_id),
            "kind": self.kind,
            "target_url": self.target_url,
            "preview": self.preview,
            "internal_access": self.internal_access,
            "marker_disclosed": self.marker_disclosed,
            "normal_success": self.normal_success,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
            "service_events": [event.to_dict() for event in self.service_events],
        }


def measure_once(
    project: MeasurementProject,
    case: ScenarioCase,
    defense: Defense,
    repetition: int,
) -> Measurement:
    """Execute one worker and inspect the internal service's trial-scoped log."""
    trial_id = uuid4()
    log_since = (datetime.now(UTC) - timedelta(seconds=2)).isoformat()
    try:
        result = project.exec_module(
            "preview",
            "ssrf_link_preview_lab.experiments.worker",
            case.name.value,
            defense.value,
            str(trial_id),
        )
        payload = json.loads(result.stdout)
        preview, trace = _validate_preview(payload, trial_id, case.target_url)
    except (OSError, RuntimeError, ValueError, TypeError) as error:
        return Measurement(
            case.name,
            defense,
            repetition,
            trial_id,
            case.kind,
            case.target_url,
            None,
            None,
            None,
            None,
            None,
            str(error),
        )

    try:
        events = tuple(
            event
            for service in ("external-page", "internal-report")
            for event in parse_trial_events(
                service,
                project.logs(service, since=log_since),
                trial_id=trial_id,
            )
        )
    except (OSError, RuntimeError, ValueError, TypeError) as error:
        return Measurement(
            case.name,
            defense,
            repetition,
            trial_id,
            case.kind,
            case.target_url,
            preview,
            None,
            None,
            None,
            float(payload["duration_seconds"]),
            str(error),
        )

    internal_access = any(
        event.service == "internal-report"
        and isinstance(event.details, InternalReportAccess)
        for event in events
    )
    internal_responses = tuple(
        hop for hop in trace.hops if hop.responder_service == "internal-report"
    )
    internal_host = (
        urlsplit(case.target_url).hostname
        if case.name is Scenario.DIRECT_INTERNAL_IP
        else "internal-report"
    )
    unconfirmed_internal_attempt = not internal_access and any(
        isinstance(event, ConnectionAttempt)
        and urlsplit(event.url).hostname == internal_host
        for event in trace.events
    )
    if (
        unconfirmed_internal_attempt
        or internal_responses
        and (
            not internal_access
            or any(
                hop.responder_trial_id != str(trial_id) for hop in internal_responses
            )
        )
    ):
        return Measurement(
            case.name,
            defense,
            repetition,
            trial_id,
            case.kind,
            case.target_url,
            preview,
            None,
            None,
            None,
            float(payload["duration_seconds"]),
            "Internal connection attempt has no matching service log"
            if unconfirmed_internal_attempt
            else "Internal response identity and service log disagree",
            events,
        )
    final_hop = trace.hops[-1] if trace.hops else None
    disclosed = (
        internal_access
        and payload["ok"] is True
        and final_hop is not None
        and final_hop.responder_service == "internal-report"
        and final_hop.responder_trial_id == str(trial_id)
        and any(
            INTERNAL_REPORT_MARKER in value
            for key in ("title", "description")
            if isinstance(value := payload.get(key), str)
        )
    )
    normal_success = (
        (
            payload["ok"] is True
            and final_hop is not None
            and final_hop.responder_service == "external-page"
            and final_hop.responder_trial_id == str(trial_id)
            and payload.get("title") == case.expected_title
            and payload.get("description") == case.expected_description
            and float(payload["duration_seconds"]) <= 10.0
        )
        if case.kind == "normal"
        else None
    )
    return Measurement(
        case.name,
        defense,
        repetition,
        trial_id,
        case.kind,
        case.target_url,
        preview,
        internal_access,
        disclosed,
        normal_success,
        float(payload["duration_seconds"]),
        service_events=events,
    )


def _validate_preview(
    payload: object, trial_id: UUID, target_url: str
) -> tuple[dict[str, object], FetchTrace]:
    if not isinstance(payload, dict):
        raise TypeError("Worker did not return a JSON object")
    if payload.get("trial_id") != str(trial_id):
        raise ValueError("Worker returned a different trial ID")
    if payload.get("requested_url") != target_url:
        raise ValueError("Worker returned a different requested URL")
    if not isinstance(payload.get("ok"), bool):
        raise TypeError("Worker omitted its preview outcome")
    duration = payload.get("duration_seconds")
    if (
        isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or not isfinite(duration)
        or duration < 0
    ):
        raise ValueError("Worker returned an invalid preview duration")
    trace = parse_fetch_trace(payload.get("trace"))
    if trace is None or not trace.events or (payload["ok"] and not trace.hops):
        raise ValueError("Worker returned an incomplete fetch trace")
    return payload, trace
