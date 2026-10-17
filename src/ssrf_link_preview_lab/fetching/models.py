"""Fetch records, with monotonic event times comparable within one process."""

from dataclasses import dataclass, field
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


@dataclass(frozen=True, slots=True)
class FetchHop:
    sequence: int
    url: str
    status_code: int
    peer_ip: str | None
    location: str | None
    redirect_url: str | None
    observed_at: float | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "url": self.url,
            "status_code": self.status_code,
            "peer_ip": self.peer_ip,
            "location": self.location,
            "redirect_url": self.redirect_url,
            "observed_at": self.observed_at,
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
            "sequence": self.sequence,
            "url": self.url,
            "resolved_addresses": list(self.resolved_addresses),
            "allowed": self.allowed,
            "reason": self.reason,
            "selected_address": self.selected_address,
            "observed_at": self.observed_at,
        }


@dataclass(frozen=True, slots=True)
class FetchTrace:
    hops: tuple[FetchHop, ...] = ()
    address_decisions: tuple[AddressDecision, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "hops": [hop.to_dict() for hop in self.hops],
            "address_decisions": [
                decision.to_dict() for decision in self.address_decisions
            ],
        }


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
