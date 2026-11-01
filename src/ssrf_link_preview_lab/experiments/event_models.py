"""Typed service events collected for an automated trial."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import ClassVar
from uuid import UUID

from ssrf_link_preview_lab.fetching.models import FetchTrace


class EventName(StrEnum):
    PREVIEW_FETCH_COMPLETED = "preview_fetch_completed"
    PREVIEW_FETCH_FAILED = "preview_fetch_failed"
    EXTERNAL_REDIRECT = "external_redirect"
    EXTERNAL_PAGE_ACCESS = "external_page_access"
    INTERNAL_REPORT_ACCESS = "internal_report_access"
    DNS_AUTHORITY_ANSWER = "dns_authority_answer"
    DNS_AUTHORITY_QUERY = "dns_authority_query"


@dataclass(frozen=True, slots=True)
class PreviewFetchCompleted:
    requested_url: str
    final_url: str
    trace: FetchTrace

    event_name: ClassVar[EventName] = EventName.PREVIEW_FETCH_COMPLETED

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_url": self.requested_url,
            "final_url": self.final_url,
            "trace": self.trace.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class PreviewFetchFailed:
    error_type: str
    message: str
    trace: FetchTrace

    event_name: ClassVar[EventName] = EventName.PREVIEW_FETCH_FAILED

    def to_dict(self) -> dict[str, object]:
        return {
            "error": self.error_type,
            "message": self.message,
            "trace": self.trace.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class ExternalRedirect:
    location: str

    event_name: ClassVar[EventName] = EventName.EXTERNAL_REDIRECT

    def to_dict(self) -> dict[str, object]:
        return {"location": self.location}


@dataclass(frozen=True, slots=True)
class ExternalPageAccess:
    event_name: ClassVar[EventName] = EventName.EXTERNAL_PAGE_ACCESS

    def to_dict(self) -> dict[str, object]:
        return {}


@dataclass(frozen=True, slots=True)
class InternalReportAccess:
    source_trial_id: UUID | None
    trial_ids_match: bool

    event_name: ClassVar[EventName] = EventName.INTERNAL_REPORT_ACCESS

    def to_dict(self) -> dict[str, object]:
        return {
            "source_trial_id": (
                str(self.source_trial_id) if self.source_trial_id is not None else None
            ),
            "trial_ids_match": self.trial_ids_match,
        }


@dataclass(frozen=True, slots=True)
class DNSAuthorityAnswer:
    hostname: str
    address: str
    ttl: int
    query: int

    event_name: ClassVar[EventName] = EventName.DNS_AUTHORITY_ANSWER

    def to_dict(self) -> dict[str, object]:
        return {
            "hostname": self.hostname,
            "address": self.address,
            "ttl": self.ttl,
            "query": self.query,
        }


@dataclass(frozen=True, slots=True)
class DNSAuthorityQuery:
    hostname: str
    record_type: str

    event_name: ClassVar[EventName] = EventName.DNS_AUTHORITY_QUERY

    def to_dict(self) -> dict[str, object]:
        return {"hostname": self.hostname, "record_type": self.record_type}


EventDetails = (
    PreviewFetchCompleted
    | PreviewFetchFailed
    | ExternalRedirect
    | ExternalPageAccess
    | InternalReportAccess
    | DNSAuthorityAnswer
    | DNSAuthorityQuery
)


@dataclass(frozen=True, slots=True)
class TrialEvent:
    timestamp: datetime
    service: str
    trial_id: UUID
    details: EventDetails

    @property
    def name(self) -> EventName:
        return self.details.event_name

    def to_dict(self) -> dict[str, object]:
        return {
            "timestamp": self.timestamp.isoformat(timespec="milliseconds"),
            "service": self.service,
            "event": self.name,
            "trial_id": str(self.trial_id),
            **self.details.to_dict(),
        }
