from datetime import UTC, datetime
from uuid import UUID

from ssrf_link_preview_lab.experiments.dns_probe import verify_dns_evidence
from ssrf_link_preview_lab.experiments.event_models import (
    DNSAuthorityAnswer,
    InternalReportAccess,
    TrialEvent,
)
from ssrf_link_preview_lab.fetching.models import AddressDecision, FetchHop, FetchTrace

_TRIAL_ID = UUID("1a2b3c4d-0000-4000-8000-000000000001")
_HOSTNAME = f"t{_TRIAL_ID.hex}.rebind.ttl0.attack.lab"
_URL = f"http://{_HOSTNAME}:8080/report"
_EXTERNAL = "172.23.0.4"
_INTERNAL = "172.24.0.4"


def _event(
    service: str, details: DNSAuthorityAnswer | InternalReportAccess
) -> TrialEvent:
    return TrialEvent(datetime.now(UTC), service, _TRIAL_ID, details)


def _check(address: str, *, allowed: bool = True) -> AddressDecision:
    return AddressDecision(
        0, _URL, (address,), allowed, "checked", address if allowed else None
    )


def _response(address: str, service: str) -> FetchHop:
    return FetchHop(
        0,
        _URL,
        200,
        address,
        None,
        None,
        responder_service=service,
        responder_trial_id=str(_TRIAL_ID),
    )


def _verify(
    trace: FetchTrace,
    *,
    answers: tuple[TrialEvent, ...],
    internal_events: tuple[TrialEvent, ...] = (),
    preview_ok: bool = True,
) -> list[str]:
    return verify_dns_evidence(
        trial_id=_TRIAL_ID,
        hostname=_HOSTNAME,
        external_ip=_EXTERNAL,
        internal_ip=_INTERNAL,
        trace=trace,
        authority_answers=answers,
        resolver_lines=[f"query: {_HOSTNAME}"],
        internal_events=internal_events,
        preview_ok=preview_ok,
    )


def test_dns_evidence_correlates_rebinding_answer_peer_and_service_log() -> None:
    answers = (
        _event("dns-authority", DNSAuthorityAnswer(f"{_HOSTNAME}.", _EXTERNAL, 0, 1)),
        _event("dns-authority", DNSAuthorityAnswer(f"{_HOSTNAME}.", _INTERNAL, 0, 2)),
    )
    trace = FetchTrace((_check(_EXTERNAL), _response(_INTERNAL, "internal-report")))
    internal_events = (_event("internal-report", InternalReportAccess(None, False)),)

    assert _verify(trace, answers=answers, internal_events=internal_events) == []
    assert "internal response and service log disagree" in _verify(
        trace, answers=answers
    )


def test_dns_evidence_accepts_an_observed_address_block() -> None:
    answers = (
        _event("dns-authority", DNSAuthorityAnswer(f"{_HOSTNAME}.", _INTERNAL, 0, 1)),
    )

    assert (
        _verify(
            FetchTrace((_check(_INTERNAL, allowed=False),)),
            answers=answers,
            preview_ok=False,
        )
        == []
    )


def test_dns_evidence_rejects_unexplained_or_unattributed_response() -> None:
    trace = FetchTrace((_check(_EXTERNAL), _response(_EXTERNAL, "external-page")))

    assert "no authority A answer for the trial hostname" in _verify(trace, answers=())
    assert "HTTP peer and service identity do not match DNS evidence" in _verify(
        trace,
        answers=(
            _event(
                "dns-authority", DNSAuthorityAnswer(f"{_HOSTNAME}.", _INTERNAL, 0, 1)
            ),
        ),
    )
