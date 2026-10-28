from collections.abc import Generator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import cast
from uuid import UUID

import pytest

from ssrf_link_preview_lab.fetching.errors import (
    FetchTimeoutError,
    InvalidRedirectUrlError,
    MissingRedirectLocationError,
    ResponseTooLargeError,
    TooManyRedirectsError,
    UpstreamHttpError,
)
from ssrf_link_preview_lab.fetching.models import (
    AddressBinding,
    AddressDecision,
    FetchFailure,
    FetchLimits,
    FetchRequest,
    TransportRequest,
    TransportResponse,
)
from ssrf_link_preview_lab.fetching.redirecting import RedirectingFetcher
from ssrf_link_preview_lab.tracing import (
    RESPONDER_SERVICE_HEADER,
    RESPONDER_TRIAL_HEADER,
    TRIAL_ID_HEADER,
)

_HTML = b"""<!doctype html>
<html>
  <head>
    <title>Controlled page</title>
    <meta name="description" content="A local integration fixture">
  </head>
</html>
"""


class _SequenceTransport:
    def __init__(self, *responses: TransportResponse) -> None:
        self._responses = iter(responses)
        self.requests: list[TransportRequest] = []

    def send(self, request: TransportRequest) -> TransportResponse:
        self.requests.append(request)
        return next(self._responses)


class _TimePassingPolicy:
    def __init__(self, clock: list[float], elapsed: float) -> None:
        self.clock = clock
        self.elapsed = elapsed

    def prepare(
        self, url: str, sequence: int, timeout_seconds: float
    ) -> tuple[tuple[AddressDecision, ...], AddressBinding | None]:
        self.clock[0] += self.elapsed
        return (), None


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        server = cast("_FixtureServer", self.server)
        server.observed_trial_ids.append(self.headers.get(TRIAL_ID_HEADER))

        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/page")
            self.send_header(RESPONDER_SERVICE_HEADER, "fixture")
            self.send_header(
                RESPONDER_TRIAL_HEADER, self.headers.get(TRIAL_ID_HEADER, "")
            )
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        body = b"x" * 128 if self.path == "/large" else _HTML
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header(RESPONDER_SERVICE_HEADER, "fixture")
        self.send_header(RESPONDER_TRIAL_HEADER, self.headers.get(TRIAL_ID_HEADER, ""))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


class _FixtureServer(ThreadingHTTPServer):
    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.observed_trial_ids: list[str | None] = []


@contextmanager
def _serve_pages() -> Generator[tuple[str, list[str | None]]]:
    server = _FixtureServer()
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        yield f"http://127.0.0.1:{server.server_port}", server.observed_trial_ids
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_fetches_page_and_follows_redirect() -> None:
    trial_id = UUID("8e6d7387-1727-45da-8c37-b0e458a2166d")
    with _serve_pages() as (base_url, observed_trial_ids):
        page = RedirectingFetcher().fetch(
            FetchRequest(url=f"{base_url}/redirect", trial_id=trial_id)
        )

    assert page.status_code == 200
    assert page.final_url == f"{base_url}/page"
    assert page.content_type == "text/html; charset=utf-8"
    assert page.peer_ip == "127.0.0.1"
    assert page.body == _HTML
    assert observed_trial_ids == [str(trial_id), str(trial_id)]
    assert [hop.responder_service for hop in page.trace.hops] == ["fixture", "fixture"]
    assert all(hop.responder_trial_id == str(trial_id) for hop in page.trace.hops)


def test_stops_when_response_exceeds_limit() -> None:
    limits = FetchLimits(max_body_bytes=32)
    trial_id = UUID("33bac9ca-4fc3-413b-8112-f5e2c0dc9300")

    with (
        _serve_pages() as (base_url, _),
        pytest.raises(ResponseTooLargeError) as caught,
    ):
        RedirectingFetcher(limits=limits).fetch(
            FetchRequest(url=f"{base_url}/large", trial_id=trial_id)
        )

    failure = caught.value.trace.events[-1]
    assert isinstance(failure, FetchFailure)
    assert failure.peer_ip == "127.0.0.1"
    assert failure.status_code == 200


def test_records_redirect_response_when_location_is_missing() -> None:
    transport = _SequenceTransport(
        _response(status_code=302, location=None),
    )

    with pytest.raises(MissingRedirectLocationError) as caught:
        RedirectingFetcher(transport=transport).fetch(
            FetchRequest(url="http://example.test/start", trial_id=UUID(int=1))
        )

    assert caught.value.trace.hops[0].status_code == 302
    assert caught.value.trace.hops[0].location is None
    assert caught.value.trace.hops[0].redirect_url is None


def test_records_redirect_response_before_rejecting_its_target() -> None:
    transport = _SequenceTransport(
        _response(status_code=302, location="ftp://example.test/file"),
    )

    with pytest.raises(InvalidRedirectUrlError) as caught:
        RedirectingFetcher(transport=transport).fetch(
            FetchRequest(url="http://example.test/start", trial_id=UUID(int=2))
        )

    assert caught.value.trace.hops[0].location == "ftp://example.test/file"
    assert caught.value.trace.hops[0].redirect_url == "ftp://example.test/file"


def test_redirect_limit_counts_completed_redirect_responses() -> None:
    transport = _SequenceTransport(
        _response(status_code=302, location="/second"),
        _response(status_code=302, location="/third"),
    )

    with pytest.raises(TooManyRedirectsError) as caught:
        RedirectingFetcher(
            transport=transport,
            limits=FetchLimits(max_redirects=1),
        ).fetch(FetchRequest(url="http://example.test/start", trial_id=UUID(int=3)))

    assert [hop.url for hop in caught.value.trace.hops] == [
        "http://example.test/start",
        "http://example.test/second",
    ]
    assert len(transport.requests) == 2


def test_http_error_retains_the_observed_status_and_response() -> None:
    transport = _SequenceTransport(_response(status_code=403, location=None))

    with pytest.raises(UpstreamHttpError) as caught:
        RedirectingFetcher(transport=transport).fetch(
            FetchRequest(url="http://example.test/forbidden", trial_id=UUID(int=4))
        )

    assert caught.value.status_code == 403
    assert caught.value.trace.hops[0].status_code == 403


def test_address_preparation_consumes_the_shared_fetch_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [0.0]
    monkeypatch.setattr(
        "ssrf_link_preview_lab.fetching.redirecting.monotonic", lambda: clock[0]
    )
    transport = _SequenceTransport(_response(status_code=200, location=None))
    fetcher = RedirectingFetcher(
        transport=transport,
        limits=FetchLimits(timeout_seconds=1.0),
        address_policy=_TimePassingPolicy(clock, 0.4),
    )

    fetcher.fetch(FetchRequest(url="http://example.test/", trial_id=UUID(int=5)))

    assert len(transport.requests) == 1
    assert transport.requests[0].timeout_seconds == pytest.approx(0.6)


def test_expired_deadline_after_address_preparation_does_not_connect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [0.0]
    monkeypatch.setattr(
        "ssrf_link_preview_lab.fetching.redirecting.monotonic", lambda: clock[0]
    )
    transport = _SequenceTransport()
    fetcher = RedirectingFetcher(
        transport=transport,
        limits=FetchLimits(timeout_seconds=1.0),
        address_policy=_TimePassingPolicy(clock, 1.0),
    )

    with pytest.raises(FetchTimeoutError) as caught:
        fetcher.fetch(FetchRequest(url="http://example.test/", trial_id=UUID(int=6)))

    assert transport.requests == []
    failure = caught.value.trace.events[-1]
    assert isinstance(failure, FetchFailure)
    assert failure.stage == "resolution"


def _response(*, status_code: int, location: str | None) -> TransportResponse:
    return TransportResponse(
        url="http://example.test/response",
        status_code=status_code,
        content_type=None,
        location=location,
        peer_ip="192.0.2.1",
        body=b"",
    )
