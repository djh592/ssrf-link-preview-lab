"""Parse trial-scoped JSON events from isolated service logs."""

import json
from datetime import datetime
from uuid import UUID

from ssrf_link_preview_lab.experiments.event_models import (
    EventDetails,
    EventName,
    ExternalPageAccess,
    ExternalRedirect,
    InternalReportAccess,
    PreviewFetchCompleted,
    PreviewFetchFailed,
    TrialEvent,
)
from ssrf_link_preview_lab.fetching.models import (
    AddressDecision,
    FetchHop,
    FetchTrace,
)


def parse_trial_events(
    service: str,
    output: str,
    *,
    trial_id: UUID,
) -> tuple[TrialEvent, ...]:
    events: list[TrialEvent] = []
    for line in output.splitlines():
        event = _parse_event(service, line)
        if event is not None and event.trial_id == trial_id:
            events.append(event)
    return tuple(events)


def _parse_event(service: str, line: str) -> TrialEvent | None:
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(record, dict):
        return None

    raw_event_name = _required_string(record, "event")
    raw_timestamp = _required_string(record, "timestamp")
    raw_trial_id = _required_string(record, "trial_id")
    if raw_event_name is None or raw_timestamp is None or raw_trial_id is None:
        return None

    try:
        event_name = EventName(raw_event_name)
        timestamp = datetime.fromisoformat(raw_timestamp)
        trial_id = UUID(raw_trial_id)
    except ValueError:
        return None
    if timestamp.tzinfo is None:
        return None

    details = _parse_details(event_name, record)
    if details is None:
        return None
    return TrialEvent(
        timestamp=timestamp,
        service=service,
        trial_id=trial_id,
        details=details,
    )


def _parse_details(
    event_name: EventName,
    record: dict[object, object],
) -> EventDetails | None:
    match event_name:
        case EventName.EXTERNAL_PAGE_ACCESS:
            return ExternalPageAccess()
        case EventName.EXTERNAL_REDIRECT:
            location = _required_string(record, "location")
            return ExternalRedirect(location) if location is not None else None
        case EventName.INTERNAL_REPORT_ACCESS:
            source_trial_id = _optional_uuid(record.get("source_trial_id"))
            trial_ids_match = record.get("trial_ids_match")
            if isinstance(source_trial_id, _InvalidValue) or not isinstance(
                trial_ids_match, bool
            ):
                return None
            return InternalReportAccess(source_trial_id, trial_ids_match)
        case EventName.PREVIEW_FETCH_COMPLETED:
            requested_url = _required_string(record, "requested_url")
            final_url = _required_string(record, "final_url")
            trace = _parse_trace(record.get("trace"))
            if requested_url is None or final_url is None or trace is None:
                return None
            return PreviewFetchCompleted(requested_url, final_url, trace)
        case EventName.PREVIEW_FETCH_FAILED:
            error_type = _required_string(record, "error")
            message = _required_string(record, "message")
            trace = _parse_trace(record.get("trace"))
            if error_type is None or message is None or trace is None:
                return None
            return PreviewFetchFailed(error_type, message, trace)


def _parse_trace(value: object) -> FetchTrace | None:
    if not isinstance(value, dict):
        return None
    raw_hops = value.get("hops")
    raw_decisions = value.get("address_decisions")
    if not isinstance(raw_hops, list) or not isinstance(raw_decisions, list):
        return None

    hops: list[FetchHop] = []
    for raw_hop in raw_hops:
        hop = _parse_hop(raw_hop)
        if hop is None:
            return None
        hops.append(hop)

    decisions: list[AddressDecision] = []
    for raw_decision in raw_decisions:
        decision = _parse_address_decision(raw_decision)
        if decision is None:
            return None
        decisions.append(decision)
    return FetchTrace(hops=tuple(hops), address_decisions=tuple(decisions))


def _parse_hop(value: object) -> FetchHop | None:
    if not isinstance(value, dict):
        return None
    sequence = _required_integer(value, "sequence")
    url = _required_string(value, "url")
    status_code = _required_integer(value, "status_code")
    peer_ip = _optional_string(value.get("peer_ip"))
    location = _optional_string(value.get("location"))
    redirect_url = _optional_string(value.get("redirect_url"))
    observed_at = _optional_number(value.get("observed_at"))
    if (
        sequence is None
        or url is None
        or status_code is None
        or isinstance(peer_ip, _InvalidValue)
        or isinstance(location, _InvalidValue)
        or isinstance(redirect_url, _InvalidValue)
        or isinstance(observed_at, _InvalidValue)
    ):
        return None
    return FetchHop(
        sequence=sequence,
        url=url,
        status_code=status_code,
        peer_ip=peer_ip,
        location=location,
        redirect_url=redirect_url,
        observed_at=observed_at,
    )


def _parse_address_decision(value: object) -> AddressDecision | None:
    if not isinstance(value, dict):
        return None
    sequence = _required_integer(value, "sequence")
    url = _required_string(value, "url")
    raw_addresses = value.get("resolved_addresses")
    allowed = value.get("allowed")
    reason = _required_string(value, "reason")
    selected_address = _optional_string(value.get("selected_address"))
    observed_at = _optional_number(value.get("observed_at"))
    if (
        sequence is None
        or url is None
        or not isinstance(raw_addresses, list)
        or not all(isinstance(address, str) for address in raw_addresses)
        or not isinstance(allowed, bool)
        or reason is None
        or isinstance(selected_address, _InvalidValue)
        or isinstance(observed_at, _InvalidValue)
    ):
        return None
    return AddressDecision(
        sequence=sequence,
        url=url,
        resolved_addresses=tuple(raw_addresses),
        allowed=allowed,
        reason=reason,
        selected_address=selected_address,
        observed_at=observed_at,
    )


class _InvalidValue:
    pass


_INVALID = _InvalidValue()


def _required_string(record: dict[object, object], field: str) -> str | None:
    value = record.get(field)
    return value if isinstance(value, str) else None


def _required_integer(record: dict[object, object], field: str) -> int | None:
    value = record.get(field)
    return value if type(value) is int else None


def _optional_string(value: object) -> str | None | _InvalidValue:
    if value is None or isinstance(value, str):
        return value
    return _INVALID


def _optional_number(value: object) -> float | None | _InvalidValue:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return _INVALID


def _optional_uuid(value: object) -> UUID | None | _InvalidValue:
    if value is None:
        return None
    if not isinstance(value, str):
        return _INVALID
    try:
        return UUID(value)
    except ValueError:
        return _INVALID
