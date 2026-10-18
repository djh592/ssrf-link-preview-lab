"""Fetch records, with monotonic event times comparable within one process."""

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class FetchRequest:
    url: str
    trial_id: UUID


@dataclass(frozen=True, slots=True)
class AddressBinding:
    """Use a selected IP for a host and port without rewriting the URL."""

    hostname: str
    port: int
    address: str


@dataclass(frozen=True, slots=True)
class TransportRequest:
    url: str
    trial_id: UUID
    timeout_seconds: float
    max_body_bytes: int
    address_binding: AddressBinding | None = None


@dataclass(frozen=True, slots=True)
class TransportResponse:
    url: str
    status_code: int
    content_type: str | None
    location: str | None
    peer_ip: str | None
    body: bytes
    responder_service: str | None = None
    responder_trial_id: str | None = None


@dataclass(frozen=True, slots=True)
class FetchHop:
    sequence: int
    url: str
    status_code: int
    peer_ip: str | None
    location: str | None
    redirect_url: str | None
    observed_at: float | None = None
    responder_service: str | None = None
    responder_trial_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "type": "http_response",
            "sequence": self.sequence,
            "url": self.url,
            "status_code": self.status_code,
            "peer_ip": self.peer_ip,
            "location": self.location,
            "redirect_url": self.redirect_url,
            "observed_at": self.observed_at,
            "responder_service": self.responder_service,
            "responder_trial_id": self.responder_trial_id,
        }


@dataclass(frozen=True, slots=True)
class AddressDecision:
    sequence: int
    url: str
    resolved_addresses: tuple[str, ...]
    allowed: bool
    reason: str
    selected_address: str | None = None
    observed_at: float | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "type": "address_decision",
            "sequence": self.sequence,
            "url": self.url,
            "resolved_addresses": list(self.resolved_addresses),
            "allowed": self.allowed,
            "reason": self.reason,
            "selected_address": self.selected_address,
            "observed_at": self.observed_at,
        }


@dataclass(frozen=True, slots=True)
class ConnectionAttempt:
    sequence: int
    url: str
    selected_address: str | None
    observed_at: float

    def to_dict(self) -> dict[str, object]:
        return {
            "type": "connection_attempt",
            "sequence": self.sequence,
            "url": self.url,
            "selected_address": self.selected_address,
            "observed_at": self.observed_at,
        }


@dataclass(frozen=True, slots=True)
class FetchFailure:
    sequence: int
    url: str
    stage: Literal["resolution", "transport"]
    reason: str
    observed_at: float
    peer_ip: str | None = None
    status_code: int | None = None
    responder_service: str | None = None
    responder_trial_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "type": "fetch_failure",
            "sequence": self.sequence,
            "url": self.url,
            "stage": self.stage,
            "reason": self.reason,
            "peer_ip": self.peer_ip,
            "status_code": self.status_code,
            "responder_service": self.responder_service,
            "responder_trial_id": self.responder_trial_id,
            "observed_at": self.observed_at,
        }


FetchEvent = AddressDecision | ConnectionAttempt | FetchHop | FetchFailure


@dataclass(frozen=True, slots=True)
class FetchTrace:
    events: tuple[FetchEvent, ...] = ()

    @property
    def hops(self) -> tuple[FetchHop, ...]:
        return tuple(event for event in self.events if isinstance(event, FetchHop))

    @property
    def address_decisions(self) -> tuple[AddressDecision, ...]:
        return tuple(
            event for event in self.events if isinstance(event, AddressDecision)
        )

    def to_dict(self) -> dict[str, object]:
        return {"events": [event.to_dict() for event in self.events]}


@dataclass(frozen=True, slots=True)
class FetchLimits:
    timeout_seconds: float = 10.0
    max_body_bytes: int = 1_000_000
    max_redirects: int = 5

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_body_bytes <= 0:
            raise ValueError("max_body_bytes must be positive")
        if self.max_redirects < 0:
            raise ValueError("max_redirects cannot be negative")


@dataclass(frozen=True, slots=True)
class FetchedPage:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str | None
    peer_ip: str | None
    body: bytes
    trace: FetchTrace = field(default_factory=FetchTrace)
