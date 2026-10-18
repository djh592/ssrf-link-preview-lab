"""Project observed fetch events onto the browser demo's network diagram."""

from dataclasses import dataclass
from ipaddress import IPv4Address
from urllib.parse import urlsplit
from uuid import UUID

from ssrf_link_preview_lab.fetching.models import (
    AddressDecision,
    ConnectionAttempt,
    FetchFailure,
    FetchHop,
    FetchTrace,
)


@dataclass(frozen=True, slots=True)
class PathStep:
    resource: str
    sequence: int
    outcome: str
    target: str
    url: str
    address: str | None
    detail: str
    observed_at: float | None
    checked_address: str | None = None
    selected_address: str | None = None
    status_code: int | None = None
    redirect_url: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "resource": self.resource,
            "sequence": self.sequence,
            "outcome": self.outcome,
            "target": self.target,
            "url": self.url,
            "address": self.address,
            "detail": self.detail,
            "observed_at": self.observed_at,
            "checked_address": self.checked_address,
            "selected_address": self.selected_address,
            "status_code": self.status_code,
            "redirect_url": self.redirect_url,
        }


@dataclass(frozen=True, slots=True)
class LabAddresses:
    external: str
    internal: str

    def target_for(self, address: str | None) -> str:
        if address == self.external and address != self.internal:
            return "external-page"
        if address == self.internal and address != self.external:
            return "internal-report"
        if address is not None:
            try:
                if IPv4Address(address).is_global:
                    return "public-web"
            except ValueError:
                pass
        return "other-address"


def project_trace(
    trace: FetchTrace,
    *,
    resource: str,
    trial_id: UUID,
    lab: LabAddresses,
) -> tuple[PathStep, ...]:
    """Return one observed outcome per attempted HTTP hop."""
    steps: list[PathStep] = []
    pending: dict[int, ConnectionAttempt] = {}
    checked: dict[int, str] = {}

    for event in trace.events:
        if isinstance(event, AddressDecision):
            if event.allowed and event.selected_address is not None:
                checked[event.sequence] = event.selected_address
            if not event.allowed:
                address = (
                    event.resolved_addresses[0] if event.resolved_addresses else None
                )
                steps.append(
                    PathStep(
                        resource,
                        event.sequence,
                        "blocked",
                        lab.target_for(address),
                        event.url,
                        address,
                        event.reason,
                        event.observed_at,
                        checked_address=checked.get(event.sequence),
                    )
                )
        elif isinstance(event, ConnectionAttempt):
            pending[event.sequence] = event
        elif isinstance(event, FetchHop):
            attempt = pending.pop(event.sequence, None)
            target, detail = _responding_target(
                event.peer_ip,
                event.responder_service,
                event.responder_trial_id,
                event.url,
                trial_id,
                lab,
            )
            steps.append(
                PathStep(
                    resource,
                    event.sequence,
                    "responded",
                    target,
                    event.url,
                    event.peer_ip,
                    detail,
                    event.observed_at,
                    checked_address=checked.get(event.sequence),
                    selected_address=(
                        attempt.selected_address if attempt is not None else None
                    ),
                    status_code=event.status_code,
                    redirect_url=event.redirect_url,
                )
            )
        elif isinstance(event, FetchFailure):
            attempt = pending.pop(event.sequence, None)
            address = event.peer_ip or (
                attempt.selected_address if attempt is not None else None
            )
            outcome = (
                "unresolved"
                if event.stage == "resolution"
                else "response_failed"
                if event.peer_ip is not None and event.status_code is not None
                else "attempted"
            )
            target = lab.target_for(address)
            detail = event.reason
            if outcome == "response_failed":
                target, responder_detail = _responding_target(
                    event.peer_ip,
                    event.responder_service,
                    event.responder_trial_id,
                    event.url,
                    trial_id,
                    lab,
                )
                detail = f"{event.reason}; {responder_detail}"
            elif outcome == "unresolved":
                target = "preview"
            steps.append(
                PathStep(
                    resource,
                    event.sequence,
                    outcome,
                    target,
                    event.url,
                    address,
                    detail,
                    event.observed_at,
                    checked_address=checked.get(event.sequence),
                    selected_address=(
                        attempt.selected_address if attempt is not None else None
                    ),
                    status_code=event.status_code,
                )
            )

    for attempt in pending.values():
        steps.append(
            PathStep(
                resource,
                attempt.sequence,
                "attempted",
                lab.target_for(attempt.selected_address),
                attempt.url,
                attempt.selected_address,
                "No connection outcome was recorded",
                attempt.observed_at,
                checked_address=checked.get(attempt.sequence),
                selected_address=attempt.selected_address,
            )
        )
    return tuple(sorted(steps, key=lambda step: (step.sequence, step.observed_at or 0)))


def _responding_target(
    peer_ip: str | None,
    service: str | None,
    observed_trial_id: str | None,
    url: str,
    trial_id: UUID,
    lab: LabAddresses,
) -> tuple[str, str]:
    address_target = lab.target_for(peer_ip)
    if address_target in {"external-page", "internal-report"}:
        if service == address_target and observed_trial_id == str(trial_id):
            return address_target, f"Confirmed by {service} and connected peer"
        return (
            "other-address",
            "Lab address responded without matching service evidence",
        )
    if service is not None:
        return "other-address", f"Unexpected service identity: {service}"
    if address_target == "public-web":
        return address_target, urlsplit(url).hostname or "Public website"
    return "other-address", "Response from an unrecognized address"
