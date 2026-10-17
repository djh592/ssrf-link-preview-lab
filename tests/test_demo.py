import socket
import subprocess
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
from ssrf_link_preview_lab.demo.policy import LabAddressPolicy
from ssrf_link_preview_lab.demo.presentation import create_presentation_app
from ssrf_link_preview_lab.experiments.compose import ComposeProject
from ssrf_link_preview_lab.fetching.errors import AddressBlockedError
from ssrf_link_preview_lab.fetching.models import (
    FetchRequest,
    TransportRequest,
    TransportResponse,
)
from ssrf_link_preview_lab.fetching.redirecting import RedirectingFetcher
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

    def lab_lookup(host: str) -> str:
        if host == "external-page":
            return EXTERNAL
        if host == "internal-report":
            return INTERNAL
        return original(host)

    monkeypatch.setattr(socket, "gethostbyname", lab_lookup)
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
        address_policy=LabAddressPolicy(defense, EXTERNAL, lab_dns),
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
    policy = LabAddressPolicy(defense, EXTERNAL, lab_dns)
    decision, binding = policy.prepare("http://rebind.lab:8080/report", 0, 2.0)

    assert decision is not None and decision.allowed
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
        address_policy=LabAddressPolicy(Defense.EACH_HOP, EXTERNAL, lab_dns),
    )

    page = fetcher.fetch(FetchRequest(url, UUID(int=4)))

    assert len(lab_dns.answers) == 2
    assert page.trace.hops[0].observed_at is not None
    assert lab_dns.answers[1].observed_at < page.trace.hops[0].observed_at


def test_direct_internal_address_is_blocked_before_http(lab_dns: DemoDNS) -> None:
    transport = _SequenceTransport()
    fetcher = RedirectingFetcher(
        transport=transport,
        address_policy=LabAddressPolicy(Defense.INITIAL, EXTERNAL, lab_dns),
    )

    with pytest.raises(AddressBlockedError) as caught:
        fetcher.fetch(FetchRequest("http://internal-report:8080/report", UUID(int=2)))

    assert transport.requests == []
    assert caught.value.trace.address_decisions[0].allowed is False


def test_outside_lab_is_blocked_even_without_defense(lab_dns: DemoDNS) -> None:
    transport = _SequenceTransport()
    fetcher = RedirectingFetcher(
        transport=transport,
        address_policy=LabAddressPolicy(Defense.NONE, EXTERNAL, lab_dns),
    )

    with pytest.raises(AddressBlockedError):
        fetcher.fetch(FetchRequest("http://example.org:8080/", UUID(int=3)))
    assert transport.requests == []


def test_demo_api_validates_state_without_serving_presentation(
    lab_dns: DemoDNS,
) -> None:
    del lab_dns
    with TestClient(create_app(settings=AppSettings(demo_enabled=True))) as client:
        assert client.get("/").status_code == 404
        assert client.get("/assets/app.js").status_code == 404
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
    assert trace["hops"] == []
    assert trace["address_decisions"][0]["allowed"] is False
    assert trial["dns_answers"] == []


def test_local_presentation_forwards_only_demo_operations(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_exec_module(
        self: ComposeProject,
        service: str,
        module: str,
        *arguments: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        del self, check
        calls.append((service, module, *arguments))
        return subprocess.CompletedProcess(
            (service, module, *arguments),
            0,
            stdout='{"status_code":200,"body":{"defense":"none"}}',
            stderr="",
        )

    monkeypatch.setattr(ComposeProject, "exec_module", fake_exec_module)
    project = ComposeProject(tmp_path, "alice-browser")
    with TestClient(create_presentation_app(project)) as client:
        assert client.get("/health").status_code == 200
        page = client.get("/")
        assert page.status_code == 200
        assert "Link Preview Security Lab" in page.text
        assert client.get("/assets/app.js").status_code == 200
        assert client.get("/preview").status_code == 404
        assert (
            client.post("/preview", json={"url": "http://example.org"}).status_code
            == 404
        )
        assert client.get("/demo/unknown").status_code == 404
        assert client.post("/demo/trial", content=b"x" * 4097).status_code == 413
        response = client.get("/demo/state")

    assert response.status_code == 200
    assert response.json() == {"defense": "none"}
    assert calls == [
        (
            "preview",
            "ssrf_link_preview_lab.demo.container_client",
            "GET",
            "/demo/state",
            "",
        )
    ]


def test_browser_launcher_rejects_a_privileged_port_without_docker(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SSRF_LAB_PORT", "80")

    assert run_browser_demo(tmp_path) == 2
