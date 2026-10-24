"""The diagram projection must distinguish response evidence from intent."""

from uuid import UUID

from ssrf_link_preview_lab.demo.observations import LabAddresses, project_observations
from ssrf_link_preview_lab.fetching.models import (
    AddressDecision,
    ConnectionAttempt,
    FetchFailure,
    FetchHop,
    FetchTrace,
)

TRIAL_ID = UUID("8c2fb32a-293f-41ea-b879-4de7c9acef3c")
LAB = LabAddresses("172.20.0.2", "172.21.0.2")


def _response(
    sequence: int,
    url: str,
    peer_ip: str | None,
    service: str | None,
    *,
    status_code: int = 200,
    redirect_url: str | None = None,
    trial_id: str | None = None,
) -> FetchHop:
    return FetchHop(
        sequence=sequence,
        url=url,
        status_code=status_code,
        peer_ip=peer_ip,
        location=redirect_url,
        redirect_url=redirect_url,
        observed_at=float(sequence + 1),
        responder_service=service,
        responder_trial_id=(
            str(TRIAL_ID) if service is not None and trial_id is None else trial_id
        ),
    )


def test_direct_internal_response_records_peer_and_confirmed_identity() -> None:
    url = "http://internal-report:8080/report"
    trace = FetchTrace(
        events=(
            ConnectionAttempt(0, url, LAB.internal, 0.1),
            _response(0, url, LAB.internal, "internal-report"),
        )
    )

    (observation,) = project_observations(
        trace, resource="page", trial_id=TRIAL_ID, lab=LAB
    )

    assert observation.outcome == "responded"
    assert observation.destination == "internal-report"
    assert observation.selected_address == LAB.internal
    assert observation.peer_address == LAB.internal
    assert observation.identity_matches is True


def test_direct_internal_block_has_no_connection_or_peer() -> None:
    url = "http://internal-report:8080/report"
    trace = FetchTrace(
        events=(
            AddressDecision(
                0,
                url,
                (LAB.internal,),
                False,
                "Non-public address blocked",
                observed_at=1.0,
            ),
        )
    )

    (observation,) = project_observations(
        trace, resource="page", trial_id=TRIAL_ID, lab=LAB
    )

    assert observation.outcome == "blocked"
    assert observation.destination == "internal-report"
    assert observation.rejected_address == LAB.internal
    assert observation.selected_address is None
    assert observation.peer_address is None


def test_redirect_has_two_preview_initiated_requests() -> None:
    external = "http://external-page:8080/redirect/internal"
    internal = "http://internal-report:8080/report"
    trace = FetchTrace(
        events=(
            ConnectionAttempt(0, external, LAB.external, 0.1),
            _response(
                0,
                external,
                LAB.external,
                "external-page",
                status_code=302,
                redirect_url=internal,
            ),
            ConnectionAttempt(1, internal, LAB.internal, 1.1),
            _response(1, internal, LAB.internal, "internal-report"),
        )
    )

    observations = project_observations(
        trace, resource="page", trial_id=TRIAL_ID, lab=LAB
    )

    assert [(item.destination, item.outcome) for item in observations] == [
        ("external-page", "responded"),
        ("internal-report", "responded"),
    ]
    assert observations[0].redirect_url == internal
    assert observations[1].url == internal


def test_redirected_internal_request_is_blocked_before_connection() -> None:
    external = "http://external-page:8080/redirect/internal"
    internal = "http://internal-report:8080/report"
    trace = FetchTrace(
        events=(
            _response(
                0,
                external,
                LAB.external,
                "external-page",
                status_code=302,
                redirect_url=internal,
            ),
            AddressDecision(
                1,
                internal,
                (LAB.internal,),
                False,
                "Non-public address blocked",
                observed_at=2.0,
            ),
        )
    )

    observations = project_observations(
        trace, resource="page", trial_id=TRIAL_ID, lab=LAB
    )

    assert observations[0].peer_address == LAB.external
    assert observations[1].outcome == "blocked"
    assert observations[1].peer_address is None


def test_rebinding_keeps_checked_selected_and_peer_addresses_distinct() -> None:
    url = "http://rebind.lab:8080/report"
    trace = FetchTrace(
        events=(
            AddressDecision(
                0, url, (LAB.external,), True, "Address check passed", LAB.external, 1.0
            ),
            ConnectionAttempt(0, url, LAB.internal, 2.0),
            _response(0, url, LAB.internal, "internal-report"),
        )
    )

    (observation,) = project_observations(
        trace, resource="page", trial_id=TRIAL_ID, lab=LAB
    )

    assert observation.checked_address == LAB.external
    assert observation.selected_address == LAB.internal
    assert observation.peer_address == LAB.internal
    assert observation.destination == "internal-report"


def test_bound_rebinding_uses_the_checked_address() -> None:
    url = "http://rebind.lab:8080/report"
    trace = FetchTrace(
        events=(
            AddressDecision(
                0, url, (LAB.external,), True, "Address check passed", LAB.external, 1.0
            ),
            ConnectionAttempt(0, url, LAB.external, 2.0),
            _response(0, url, LAB.external, "external-page"),
        )
    )

    (observation,) = project_observations(
        trace, resource="page", trial_id=TRIAL_ID, lab=LAB
    )

    assert observation.checked_address == observation.selected_address == LAB.external
    assert observation.peer_address == LAB.external
    assert observation.destination == "external-page"


def test_public_response_uses_peer_without_claiming_lab_identity() -> None:
    url = "https://example.org/"
    trace = FetchTrace(events=(_response(0, url, "93.184.216.34", None),))

    (observation,) = project_observations(
        trace, resource="page", trial_id=TRIAL_ID, lab=LAB
    )

    assert observation.destination == "public-web"
    assert observation.peer_address == "93.184.216.34"
    assert observation.identity_matches is None


def test_misrouted_hostname_uses_actual_peer_not_url_hostname() -> None:
    trace = FetchTrace(
        events=(
            _response(
                0, "http://external-page:8080/page", LAB.internal, "internal-report"
            ),
        )
    )

    (observation,) = project_observations(
        trace, resource="page", trial_id=TRIAL_ID, lab=LAB
    )

    assert observation.destination == "internal-report"
    assert observation.identity_matches is True
    assert observation.url.startswith("http://external-page")


def test_identity_mismatch_does_not_hide_the_actual_peer() -> None:
    trace = FetchTrace(
        events=(
            _response(
                0, "http://external-page:8080/page", LAB.internal, "external-page"
            ),
        )
    )

    (observation,) = project_observations(
        trace, resource="page", trial_id=TRIAL_ID, lab=LAB
    )

    assert observation.destination == "internal-report"
    assert observation.peer_address == LAB.internal
    assert observation.responder_service == "external-page"
    assert observation.identity_matches is False


def test_transport_timeout_does_not_claim_delivery() -> None:
    url = "https://www.python.org/"
    trace = FetchTrace(
        events=(
            ConnectionAttempt(0, url, "151.101.64.223", 1.0),
            FetchFailure(0, url, "transport", "Connection timed out", 2.0),
        )
    )

    (observation,) = project_observations(
        trace, resource="page", trial_id=TRIAL_ID, lab=LAB
    )

    assert observation.destination == "public-web"
    assert observation.outcome == "attempted"
    assert observation.selected_address == "151.101.64.223"
    assert observation.peer_address is None


def test_received_headers_remain_visible_when_body_transfer_fails() -> None:
    url = "http://internal-report:8080/report"
    trace = FetchTrace(
        events=(
            ConnectionAttempt(0, url, LAB.internal, 1.0),
            FetchFailure(
                0,
                url,
                "transport",
                "Body limit exceeded",
                2.0,
                LAB.internal,
                200,
                "internal-report",
                str(TRIAL_ID),
            ),
        )
    )

    (observation,) = project_observations(
        trace, resource="page", trial_id=TRIAL_ID, lab=LAB
    )

    assert observation.outcome == "response_failed"
    assert observation.peer_address == LAB.internal
    assert observation.status_code == 200
    assert observation.identity_matches is True


def test_response_without_peer_does_not_invent_a_route() -> None:
    trace = FetchTrace(events=(_response(0, "https://example.org/", None, None),))

    (observation,) = project_observations(
        trace, resource="page", trial_id=TRIAL_ID, lab=LAB
    )

    assert observation.outcome == "responded"
    assert observation.destination is None
    assert observation.peer_address is None


def test_image_fetch_is_a_separate_observation() -> None:
    url = "https://example.org/cover.png"
    trace = FetchTrace(events=(_response(0, url, "93.184.216.34", None),))

    (observation,) = project_observations(
        trace, resource="image", trial_id=TRIAL_ID, lab=LAB
    )

    assert observation.resource == "image"
    assert observation.sequence == 0
    assert observation.destination == "public-web"
