"""Parse trial-scoped JSON events from isolated service logs."""

import json
from datetime import datetime
from uuid import UUID

from ssrf_link_preview_lab.experiments.event_models import (
    DNSAuthorityAnswer,
    DNSAuthorityQuery,
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
    ConnectionAttempt,
    FetchEvent,
    FetchFailure,
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
        case EventName.DNS_AUTHORITY_ANSWER:
            hostname = _required_string(record, "hostname")
            address = _required_string(record, "address")
            ttl = _required_integer(record, "ttl")
            query = _required_integer(record, "query")
            if hostname is None or address is None or ttl is None or query is None:
                return None
            return DNSAuthorityAnswer(hostname, address, ttl, query)
        case EventName.DNS_AUTHORITY_QUERY:
            hostname = _required_string(record, "hostname")
            record_type = _required_string(record, "record_type")
            if hostname is None or record_type is None:
                return None
            return DNSAuthorityQuery(hostname, record_type)
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
            trace = parse_fetch_trace(record.get("trace"))
            if requested_url is None or final_url is None or trace is None:
                return None
            return PreviewFetchCompleted(requested_url, final_url, trace)
        case EventName.PREVIEW_FETCH_FAILED:
            error_type = _required_string(record, "error")
            message = _required_string(record, "message")
            trace = parse_fetch_trace(record.get("trace"))
            if error_type is None or message is None or trace is None:
                return None
            return PreviewFetchFailed(error_type, message, trace)


def parse_fetch_trace(value: object) -> FetchTrace | None:
    """Decode a fetch trace returned by a trusted lab worker or service log."""
    if not isinstance(value, dict):
        return None
    raw_events = value.get("events")
    if not isinstance(raw_events, list):
        return None

    events: list[FetchEvent] = []
    for raw_event in raw_events:
        event = _parse_fetch_event(raw_event)
        if event is None:
            return None
        events.append(event)
    return FetchTrace(events=tuple(events))


def _parse_fetch_event(value: object) -> FetchEvent | None:
    if not isinstance(value, dict):
        return None
    match value.get("type"):
        case "http_response":
            return _parse_hop(value)
        case "address_decision":
            return _parse_address_decision(value)
        case "connection_attempt":
            sequence = _required_integer(value, "sequence")
            url = _required_string(value, "url")
            address = _optional_string(value.get("selected_address"))
            observed_at = _optional_number(value.get("observed_at"))
            if (
                sequence is None
                or url is None
                or isinstance(address, _InvalidValue)
                or not isinstance(observed_at, float)
            ):
                return None
            return ConnectionAttempt(sequence, url, address, observed_at)
        case "fetch_failure":
            return _parse_fetch_failure(value)
        case _:
            return None


def _parse_fetch_failure(value: dict[object, object]) -> FetchFailure | None:
    sequence = _required_integer(value, "sequence")
    url = _required_string(value, "url")
    stage = _required_string(value, "stage")
    reason = _required_string(value, "reason")
    peer_ip = _optional_string(value.get("peer_ip"))
    status_code = _optional_integer(value.get("status_code"))
    responder_service = _optional_string(value.get("responder_service"))
    responder_trial_id = _optional_string(value.get("responder_trial_id"))
    observed_at = _optional_number(value.get("observed_at"))
    if (
        sequence is None
        or url is None
        or stage not in {"resolution", "transport"}
        or reason is None
        or isinstance(peer_ip, _InvalidValue)
        or isinstance(status_code, _InvalidValue)
        or isinstance(responder_service, _InvalidValue)
        or isinstance(responder_trial_id, _InvalidValue)
        or not isinstance(observed_at, float)
    ):
        return None
    return FetchFailure(
        sequence,
        url,
        stage,
        reason,
        observed_at,
        peer_ip,
        status_code,
        responder_service,
        responder_trial_id,
    )


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
    responder_service = _optional_string(value.get("responder_service"))
    responder_trial_id = _optional_string(value.get("responder_trial_id"))
    if (
        sequence is None
        or url is None
        or status_code is None
        or isinstance(peer_ip, _InvalidValue)
        or isinstance(location, _InvalidValue)
        or isinstance(redirect_url, _InvalidValue)
        or isinstance(observed_at, _InvalidValue)
        or isinstance(responder_service, _InvalidValue)
        or isinstance(responder_trial_id, _InvalidValue)
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
        responder_service=responder_service,
        responder_trial_id=responder_trial_id,
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


def _optional_integer(value: object) -> int | None | _InvalidValue:
    if value is None or type(value) is int:
        return value
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
