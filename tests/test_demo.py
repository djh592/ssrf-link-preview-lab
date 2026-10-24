import socket
from collections.abc import Generator
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from ssrf_link_preview_lab.api.app import create_app
from ssrf_link_preview_lab.demo.cli import run_browser_demo
from ssrf_link_preview_lab.demo.controller import DemoController
from ssrf_link_preview_lab.demo.dns import DemoDNS
from ssrf_link_preview_lab.demo.models import Defense, DemoState, DNSMode
from ssrf_link_preview_lab.demo.policy import DemoAddressPolicy
from ssrf_link_preview_lab.fetching.errors import AddressBlockedError
from ssrf_link_preview_lab.fetching.models import (
    FetchRequest,
    TransportRequest,
    TransportResponse,
)
from ssrf_link_preview_lab.fetching.redirecting import RedirectingFetcher
from ssrf_link_preview_lab.preview.service import PreviewService
from ssrf_link_preview_lab.settings import AppSettings

EXTERNAL = "198.51.100.10"
INTERNAL = "198.51.100.20"


class _SequenceTransport:
    def __init__(self, *responses: TransportResponse) -> None:
        self.responses = iter(responses)
        self.requests: list[TransportRequest] = []

    def send(self, request: TransportRequest) -> TransportResponse:
        self.requests.append(request)
        return next(self.responses)


def _response(url: str, status: int, location: str | None = None) -> TransportResponse:
    return TransportResponse(
        url=url,
        status_code=status,
        content_type="text/html",
        location=location,
        peer_ip=INTERNAL if "internal-report" in url else EXTERNAL,
        body=b"<title>Lab</title>",
    )


@pytest.fixture
def lab_dns(monkeypatch: MonkeyPatch) -> Generator[DemoDNS]:
    original = socket.gethostbyname
    original_lookup = DemoDNS.lookup

    def lab_lookup(host: str) -> str:
        if host == "external-page":
            return EXTERNAL
        if host == "internal-report":
            return INTERNAL
        return original(host)

    monkeypatch.setattr(socket, "gethostbyname", lab_lookup)

    def lookup(self: DemoDNS, hostname: str, timeout_seconds: float) -> str:
        if hostname in {"external-page", "internal-report"}:
            return lab_lookup(hostname)
        if hostname == "example.org":
            return "93.184.216.34"
        return original_lookup(self, hostname, timeout_seconds)

    monkeypatch.setattr(DemoDNS, "lookup", lookup)
    dns = DemoDNS()
    dns.configure(EXTERNAL, INTERNAL, rebind=True)
    yield dns
    dns.close()


@pytest.mark.parametrize(
    ("defense", "expected_requests", "blocked"),
    [
        (Defense.NONE, 2, False),
        (Defense.INITIAL, 2, False),
        (Defense.EACH_HOP, 1, True),
        (Defense.BOUND, 1, True),
    ],
)
def test_redirect_policy_matrix(
    lab_dns: DemoDNS,
    defense: Defense,
    expected_requests: int,
    blocked: bool,
) -> None:
    external = "http://external-page:8080/redirect/internal"
    internal = "http://internal-report:8080/report"
    transport = _SequenceTransport(
        _response(external, 302, internal), _response(internal, 200)
    )
    fetcher = RedirectingFetcher(
        transport=transport,
        address_policy=DemoAddressPolicy(defense, EXTERNAL, INTERNAL, lab_dns),
    )
    request = FetchRequest(external, UUID(int=1))

    if blocked:
        with pytest.raises(AddressBlockedError) as caught:
            fetcher.fetch(request)
        assert caught.value.trace.address_decisions[-1].resolved_addresses == (
            INTERNAL,
        )
        assert len(caught.value.trace.hops) == 1
    else:
        page = fetcher.fetch(request)
        assert page.peer_ip == INTERNAL
        assert len(page.trace.hops) == 2
    assert len(transport.requests) == expected_requests


@pytest.mark.parametrize(
    ("defense", "answers", "peer"),
    [
        (Defense.EACH_HOP, (EXTERNAL, INTERNAL), INTERNAL),
        (Defense.BOUND, (EXTERNAL,), EXTERNAL),
    ],
)
def test_rebinding_queries_and_checked_address_binding(
    lab_dns: DemoDNS, defense: Defense, answers: tuple[str, ...], peer: str
) -> None:
    policy = DemoAddressPolicy(defense, EXTERNAL, INTERNAL, lab_dns)
    decisions, binding = policy.prepare("http://rebind.lab:8080/report", 0, 2.0)

    (decision,) = decisions
    assert decision.allowed
    assert decision.resolved_addresses == (EXTERNAL,)
    assert binding is not None and binding.address == peer
    assert tuple(answer.address for answer in lab_dns.answers) == answers
    assert decision.observed_at is not None
    assert lab_dns.answers[0].observed_at < decision.observed_at
    if defense is Defense.EACH_HOP:
        assert decision.observed_at < lab_dns.answers[1].observed_at


def test_http_hop_is_recorded_after_connection_stage_dns(lab_dns: DemoDNS) -> None:
    url = "http://rebind.lab:8080/report"
    fetcher = RedirectingFetcher(
        transport=_SequenceTransport(_response(url, 200)),
        address_policy=DemoAddressPolicy(Defense.EACH_HOP, EXTERNAL, INTERNAL, lab_dns),
    )

    page = fetcher.fetch(FetchRequest(url, UUID(int=4)))

    assert len(lab_dns.answers) == 2
    assert page.trace.hops[0].observed_at is not None
    assert lab_dns.answers[1].observed_at < page.trace.hops[0].observed_at


def test_direct_internal_address_is_blocked_before_http(lab_dns: DemoDNS) -> None:
    transport = _SequenceTransport()
    fetcher = RedirectingFetcher(
        transport=transport,
        address_policy=DemoAddressPolicy(Defense.INITIAL, EXTERNAL, INTERNAL, lab_dns),
    )

    with pytest.raises(AddressBlockedError) as caught:
        fetcher.fetch(FetchRequest("http://internal-report:8080/report", UUID(int=2)))

    assert transport.requests == []
    assert caught.value.trace.address_decisions[0].allowed is False


def test_non_web_port_is_blocked_even_without_defense(lab_dns: DemoDNS) -> None:
    transport = _SequenceTransport()
    fetcher = RedirectingFetcher(
        transport=transport,
        address_policy=DemoAddressPolicy(Defense.NONE, EXTERNAL, INTERNAL, lab_dns),
    )

    with pytest.raises(AddressBlockedError):
        fetcher.fetch(FetchRequest("http://example.org:8080/", UUID(int=3)))
    assert transport.requests == []


def test_public_page_uses_the_same_fetcher(lab_dns: DemoDNS) -> None:
    url = "https://example.org/article"
    transport = _SequenceTransport(_response(url, 200))
    fetcher = RedirectingFetcher(
        transport=transport,
        address_policy=DemoAddressPolicy(Defense.NONE, EXTERNAL, INTERNAL, lab_dns),
    )

    page = fetcher.fetch(FetchRequest(url, UUID(int=5)))

    assert page.status_code == 200
    assert transport.requests[0].address_binding is not None
    assert transport.requests[0].address_binding.address == "93.184.216.34"


@pytest.mark.parametrize("address", ["127.0.0.1", "10.4.2.1", "169.254.169.254"])
def test_real_private_destinations_are_blocked_before_http(
    lab_dns: DemoDNS, monkeypatch: MonkeyPatch, address: str
) -> None:
    monkeypatch.setattr(lab_dns, "lookup", lambda *_: address)
    transport = _SequenceTransport()
    fetcher = RedirectingFetcher(
        transport=transport,
        address_policy=DemoAddressPolicy(Defense.NONE, EXTERNAL, INTERNAL, lab_dns),
    )

    with pytest.raises(AddressBlockedError):
        fetcher.fetch(FetchRequest("http://untrusted.example/", UUID(int=6)))

    assert transport.requests == []


def test_public_redirect_to_real_private_address_is_blocked(
    lab_dns: DemoDNS, monkeypatch: MonkeyPatch
) -> None:
    def lookup(hostname: str, _timeout_seconds: float) -> str:
        return "10.8.0.4" if hostname == "private.example" else "93.184.216.34"

    monkeypatch.setattr(lab_dns, "lookup", lookup)
    start = "https://public.example/start"
    transport = _SequenceTransport(_response(start, 302, "http://private.example/"))
    fetcher = RedirectingFetcher(
        transport=transport,
        address_policy=DemoAddressPolicy(Defense.NONE, EXTERNAL, INTERNAL, lab_dns),
    )

    with pytest.raises(AddressBlockedError) as caught:
        fetcher.fetch(FetchRequest(start, UUID(int=7)))

    assert len(transport.requests) == 1
    assert caught.value.trace.hops[0].status_code == 302
    assert caught.value.trace.address_decisions[-1].resolved_addresses == ("10.8.0.4",)


def test_second_dns_answer_cannot_reach_real_private_network(
    lab_dns: DemoDNS, monkeypatch: MonkeyPatch
) -> None:
    answers = iter(("93.184.216.34", "192.168.1.1"))
    monkeypatch.setattr(lab_dns, "lookup", lambda *_: next(answers))
    transport = _SequenceTransport()
    fetcher = RedirectingFetcher(
        transport=transport,
        address_policy=DemoAddressPolicy(Defense.EACH_HOP, EXTERNAL, INTERNAL, lab_dns),
    )

    with pytest.raises(AddressBlockedError) as caught:
        fetcher.fetch(FetchRequest("https://untrusted.example/", UUID(int=8)))

    assert transport.requests == []
    assert caught.value.trace.address_decisions[0].allowed is True
    assert caught.value.trace.address_decisions[1].allowed is False


def test_image_url_to_real_private_network_does_not_make_an_http_request(
    lab_dns: DemoDNS,
) -> None:
    url = "https://example.org/story"
    transport = _SequenceTransport(
        TransportResponse(
            url=url,
            status_code=200,
            content_type="text/html",
            location=None,
            peer_ip="93.184.216.34",
            body=b'<title>Public article</title><meta property="og:image" '
            b'content="http://10.0.0.9/private.png">',
        )
    )
    service = PreviewService(
        RedirectingFetcher(
            transport=transport,
            address_policy=DemoAddressPolicy(Defense.NONE, EXTERNAL, INTERNAL, lab_dns),
        )
    )

    preview = service.create(url, trial_id=UUID(int=9))

    assert preview.title == "Public article"
    assert preview.image_data_url is None
    assert preview.image_trace.address_decisions[-1].allowed is False
    assert len(transport.requests) == 1


def test_demo_api_serves_ui_and_validates_state(
    lab_dns: DemoDNS,
) -> None:
    del lab_dns
    with TestClient(create_app(settings=AppSettings(demo_enabled=True))) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert page.text.index('class="preview-stage"') < page.text.index(
            'class="network-stage"'
        )
        assert client.get("/assets/app.js").status_code == 200
        assert client.get("/assets/topology.js").status_code == 200
        assert client.get("/assets/topology.css").status_code == 200
        assert client.get("/favicon.ico").status_code == 200
        response = client.put(
            "/demo/state",
            json={"defense": "each_hop", "dns_mode": "rebind"},
        )
        assert response.status_code == 200
        assert response.json()["defense"] == "each_hop"
        assert "redirect" not in response.json()
        assert (
            client.put(
                "/demo/state",
                json={"defense": "none", "dns_mode": "stable", "redirect": "internal"},
            ).status_code
            == 422
        )
        assert (
            client.put(
                "/demo/state",
                json={"defense": "unknown", "dns_mode": "stable"},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/preview", json={"url": "http://external-page:8080/page"}
            ).status_code
            == 503
        )


def test_demo_trial_reports_blocked_decision(
    lab_dns: DemoDNS,
) -> None:
    del lab_dns
    controller = DemoController()
    try:
        controller.configure(DemoState(Defense.INITIAL, DNSMode.STABLE))
        trial = controller.run("http://internal-report:8080/report")
    finally:
        controller.close()
    assert trial["ok"] is False
    trace = trial["trace"]
    assert isinstance(trace, dict)
    assert trace["events"][0]["type"] == "address_decision"
    assert trace["events"][0]["allowed"] is False
    observations = trial["observations"]
    assert isinstance(observations, list)
    assert observations[0]["outcome"] == "blocked"
    assert observations[0]["destination"] == "internal-report"
    assert observations[0]["peer_address"] is None
    assert trial["dns_answers"] == []


def test_browser_launcher_rejects_a_privileged_port_without_docker(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SSRF_LAB_PORT", "80")

    assert run_browser_demo(tmp_path) == 2


def test_browser_launcher_requires_explicit_public_egress(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("SSRF_LAB_PUBLIC_EGRESS", raising=False)
    monkeypatch.setenv("SSRF_LAB_PORT", "8765")

    assert run_browser_demo(tmp_path) == 2
