from collections.abc import Generator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from ssrf_link_preview_lab.fetching.errors import ResponseTooLargeError
from ssrf_link_preview_lab.fetching.models import FetchLimits
from ssrf_link_preview_lab.fetching.pycurl import PycurlFetcher

_HTML = b"""<!doctype html>
<html>
  <head>
    <title>Controlled page</title>
    <meta name="description" content="A local integration fixture">
  </head>
</html>
"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/page")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        body = b"x" * 128 if self.path == "/large" else _HTML
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


@contextmanager
def _serve_pages() -> Generator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_fetches_page_and_follows_redirect() -> None:
    with _serve_pages() as base_url:
        page = PycurlFetcher().fetch(f"{base_url}/redirect")

    assert page.status_code == 200
    assert page.final_url == f"{base_url}/page"
    assert page.content_type == "text/html; charset=utf-8"
    assert page.peer_ip == "127.0.0.1"
    assert page.body == _HTML


def test_stops_when_response_exceeds_limit() -> None:
    limits = FetchLimits(max_body_bytes=32)

    with _serve_pages() as base_url, pytest.raises(ResponseTooLargeError):
        PycurlFetcher(limits).fetch(f"{base_url}/large")
