"""Summarize recorded fetch events without inferring packet delivery."""

from dataclasses import dataclass
from ipaddress import IPv4Address
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from ssrf_link_preview_lab.fetching.models import (
    AddressDecision,
    ConnectionAttempt,
    FetchFailure,
    FetchHop,
    FetchTrace,
)

type Resource = Literal["page", "image"]
type Outcome = Literal[
    "responded", "response_failed", "blocked", "attempted", "unresolved"
]


@dataclass(frozen=True, slots=True)
class LabAddresses:
    """Addresses assigned to the two lab services for this trial."""

    external: str
    internal: str

    def destination_for(self, address: str | None) -> str | None:
        if address is None:
            return None
        if address == self.external and address != self.internal:
            return "external-page"
        if address == self.internal and address != self.external:
            return "internal-report"
        try:
            if IPv4Address(address).is_global:
                return "public-web"
        except ValueError:
            pass
        return "other-address"


@dataclass(frozen=True, slots=True)
class ObservedRequest:
    """One HTTP hop's outcome, keeping decisions separate from received evidence."""

    resource: Resource
    sequence: int
    url: str
    outcome: Outcome
    destination: str | None
    observed_at: float | None
    detail: str
    checked_address: str | None = None
    rejected_address: str | None = None
    selected_address: str | None = None
    peer_address: str | None = None
    status_code: int | None = None
    redirect_url: str | None = None
    responder_service: str | None = None
    identity_matches: bool | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "resource": self.resource,
            "sequence": self.sequence,
            "url": self.url,
            "outcome": self.outcome,
            "destination": self.destination,
            "observed_at": self.observed_at,
            "detail": self.detail,
            "checked_address": self.checked_address,
            "rejected_address": self.rejected_address,
            "selected_address": self.selected_address,
            "peer_address": self.peer_address,
            "status_code": self.status_code,
            "redirect_url": self.redirect_url,
            "responder_service": self.responder_service,
            "identity_matches": self.identity_matches,
        }


def project_observations(
    trace: FetchTrace,
    *,
    resource: Resource,
    trial_id: UUID,
    lab: LabAddresses,
) -> tuple[ObservedRequest, ...]:
    """Project each attempted HTTP hop from the ordered fetch trace."""
    observations: list[ObservedRequest] = []
    attempts: dict[int, ConnectionAttempt] = {}
    checked: dict[int, str] = {}

    for event in trace.events:
        if isinstance(event, AddressDecision):
            if event.allowed:
                if event.selected_address is not None:
                    checked[event.sequence] = event.selected_address
                continue
            rejected = next(iter(event.resolved_addresses), None)
            observations.append(
                ObservedRequest(
                    resource=resource,
                    sequence=event.sequence,
                    url=event.url,
                    outcome="blocked",
                    destination=lab.destination_for(rejected),
                    observed_at=event.observed_at,
                    detail=event.reason,
                    checked_address=checked.get(event.sequence),
                    rejected_address=rejected,
                )
            )
        elif isinstance(event, ConnectionAttempt):
            attempts[event.sequence] = event
        elif isinstance(event, FetchHop):
            attempt = attempts.pop(event.sequence, None)
            destination, detail, identity_matches = _response_identity(
                event.peer_ip,
                event.responder_service,
                event.responder_trial_id,
                event.url,
                trial_id,
                lab,
            )
            observations.append(
                ObservedRequest(
                    resource=resource,
                    sequence=event.sequence,
                    url=event.url,
                    outcome="responded",
                    destination=destination,
                    observed_at=event.observed_at,
                    detail=detail,
                    checked_address=checked.get(event.sequence),
                    selected_address=(
                        attempt.selected_address if attempt is not None else None
                    ),
                    peer_address=event.peer_ip,
                    status_code=event.status_code,
                    redirect_url=event.redirect_url,
                    responder_service=event.responder_service,
                    identity_matches=identity_matches,
                )
            )
        elif isinstance(event, FetchFailure):
            attempt = attempts.pop(event.sequence, None)
            selected = attempt.selected_address if attempt is not None else None
            outcome: Outcome = (
                "unresolved"
                if event.stage == "resolution"
                else "response_failed"
                if event.status_code is not None
                else "attempted"
            )
            address = event.peer_ip or selected
            destination = lab.destination_for(address)
            detail = event.reason
            identity_matches = None
            if outcome == "response_failed":
                destination, response_detail, identity_matches = _response_identity(
                    event.peer_ip,
                    event.responder_service,
                    event.responder_trial_id,
                    event.url,
                    trial_id,
                    lab,
                )
                detail = f"{event.reason}; {response_detail}"
            elif outcome == "unresolved":
                destination = None
            observations.append(
                ObservedRequest(
                    resource=resource,
                    sequence=event.sequence,
                    url=event.url,
                    outcome=outcome,
                    destination=destination,
                    observed_at=event.observed_at,
                    detail=detail,
                    checked_address=checked.get(event.sequence),
                    selected_address=selected,
                    peer_address=event.peer_ip,
                    status_code=event.status_code,
                    responder_service=event.responder_service,
                    identity_matches=identity_matches,
                )
            )

    for attempt in attempts.values():
        observations.append(
            ObservedRequest(
                resource=resource,
                sequence=attempt.sequence,
                url=attempt.url,
                outcome="attempted",
                destination=lab.destination_for(attempt.selected_address),
                observed_at=attempt.observed_at,
                detail="No connection outcome was recorded",
                checked_address=checked.get(attempt.sequence),
                selected_address=attempt.selected_address,
            )
        )
    return tuple(
        sorted(
            observations,
            key=lambda observation: (
                observation.sequence,
                observation.observed_at or 0,
            ),
        )
    )


def _response_identity(
    peer_ip: str | None,
    service: str | None,
    observed_trial_id: str | None,
    url: str,
    trial_id: UUID,
    lab: LabAddresses,
) -> tuple[str | None, str, bool | None]:
    destination = lab.destination_for(peer_ip)
    if destination in {"external-page", "internal-report"}:
        matches = service == destination and observed_trial_id == str(trial_id)
        detail = (
            "Lab response confirmed by peer and trial identity"
            if matches
            else "Lab peer responded without matching service and trial identity"
        )
        return destination, detail, matches
    if service is not None or observed_trial_id is not None:
        return destination, "Unexpected lab identity in response", False
    if destination == "public-web":
        return destination, urlsplit(url).hostname or "Public website", None
    if peer_ip is None:
        return None, "HTTP response received; peer address unavailable", None
    return destination, "Response from an unrecognized address", None
