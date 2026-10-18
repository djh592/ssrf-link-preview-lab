from uuid import UUID

from ssrf_link_preview_lab.demo.topology import LabAddresses, project_trace
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
    peer_ip: str,
    service: str | None,
    *,
    status_code: int = 200,
    redirect_url: str | None = None,
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
        responder_trial_id=str(TRIAL_ID) if service is not None else None,
    )


def test_redirect_path_uses_actual_responders_not_location_as_an_edge() -> None:
    trace = FetchTrace(
        events=(
            ConnectionAttempt(
                0, "http://external-page:8080/redirect/internal", LAB.external, 0.1
            ),
            _response(
                0,
                "http://external-page:8080/redirect/internal",
                LAB.external,
                "external-page",
                status_code=302,
                redirect_url="http://internal-report:8080/report",
            ),
            ConnectionAttempt(
                1, "http://internal-report:8080/report", LAB.internal, 1.1
            ),
            _response(
                1, "http://internal-report:8080/report", LAB.internal, "internal-report"
            ),
        )
    )

    steps = project_trace(trace, resource="page", trial_id=TRIAL_ID, lab=LAB)

    assert [(step.target, step.outcome) for step in steps] == [
        ("external-page", "responded"),
        ("internal-report", "responded"),
    ]
    assert steps[0].redirect_url == "http://internal-report:8080/report"


def test_blocked_target_is_not_reported_as_reached() -> None:
    trace = FetchTrace(
        events=(
            _response(
                0,
                "http://external-page:8080/redirect/internal",
                LAB.external,
                "external-page",
                status_code=302,
                redirect_url="http://internal-report:8080/report",
            ),
            AddressDecision(
                1,
                "http://internal-report:8080/report",
                (LAB.internal,),
                False,
                "Non-public address blocked",
                observed_at=2.0,
            ),
        )
    )

    steps = project_trace(trace, resource="page", trial_id=TRIAL_ID, lab=LAB)

    assert [(step.target, step.outcome) for step in steps] == [
        ("external-page", "responded"),
        ("internal-report", "blocked"),
    ]


def test_rebinding_displays_checked_and_connected_addresses_separately() -> None:
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

    (step,) = project_trace(trace, resource="page", trial_id=TRIAL_ID, lab=LAB)

    assert step.target == "internal-report"
    assert step.checked_address == LAB.external
    assert step.selected_address == LAB.internal
    assert step.address == LAB.internal


def test_transport_failure_does_not_claim_delivery() -> None:
    url = "https://www.python.org/"
    trace = FetchTrace(
        events=(
            ConnectionAttempt(0, url, "151.101.64.223", 1.0),
            FetchFailure(0, url, "transport", "Connection timed out", 2.0),
        )
    )

    (step,) = project_trace(trace, resource="page", trial_id=TRIAL_ID, lab=LAB)

    assert step.target == "public-web"
    assert step.outcome == "attempted"
    assert step.address == "151.101.64.223"


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

    (step,) = project_trace(trace, resource="page", trial_id=TRIAL_ID, lab=LAB)

    assert step.outcome == "response_failed"
    assert step.target == "internal-report"
    assert step.status_code == 200


def test_unexpected_service_identity_is_not_forced_into_expected_node() -> None:
    trace = FetchTrace(
        events=(
            _response(
                0, "http://external-page:8080/page", LAB.internal, "external-page"
            ),
        )
    )

    (step,) = project_trace(trace, resource="page", trial_id=TRIAL_ID, lab=LAB)

    assert step.target == "other-address"
    assert "without matching service evidence" in step.detail


def test_misrouted_hostname_follows_the_actual_internal_responder() -> None:
    trace = FetchTrace(
        events=(
            _response(
                0, "http://external-page:8080/page", LAB.internal, "internal-report"
            ),
        )
    )

    (step,) = project_trace(trace, resource="page", trial_id=TRIAL_ID, lab=LAB)

    assert step.target == "internal-report"
    assert step.url == "http://external-page:8080/page"


def test_unrecognized_public_destination_uses_observed_peer() -> None:
    trace = FetchTrace(
        events=(_response(0, "https://example.org/", "93.184.216.34", None),)
    )

    (step,) = project_trace(trace, resource="page", trial_id=TRIAL_ID, lab=LAB)

    assert step.target == "public-web"
    assert step.address == "93.184.216.34"
    assert step.detail == "example.org"
