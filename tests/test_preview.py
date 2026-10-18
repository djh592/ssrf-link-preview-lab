from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from ssrf_link_preview_lab.api.app import create_app
from ssrf_link_preview_lab.fetching.errors import TransportError
from ssrf_link_preview_lab.fetching.models import (
    FetchedPage,
    FetchHop,
    FetchRequest,
    FetchTrace,
)
from ssrf_link_preview_lab.preview.errors import UnsupportedContentTypeError
from ssrf_link_preview_lab.preview.parser import parse_html_metadata
from ssrf_link_preview_lab.preview.service import PreviewService


class _StubFetcher:
    def __init__(self) -> None:
        self.requests: list[FetchRequest] = []

    def fetch(self, request: FetchRequest) -> FetchedPage:
        self.requests.append(request)
        return FetchedPage(
            requested_url=request.url,
            final_url="https://example.test/final",
            status_code=200,
            content_type="text/html; charset=utf-8",
            peer_ip="192.0.2.10",
            body=b"""
                <title>Document title</title>
                <meta name="description" content="Fallback description">
                <meta property="og:title" content="Preview title">
                <meta property="og:description" content="Preview description">
            """,
        )


class _FailingFetcher:
    def __init__(self) -> None:
        self.request: FetchRequest | None = None

    def fetch(self, request: FetchRequest) -> FetchedPage:
        self.request = request
        raise TransportError(7, "controlled failure")


def test_preview_returns_page_metadata() -> None:
    fetcher = _StubFetcher()
    with TestClient(create_app(fetcher=fetcher)) as client:
        response = client.post("/preview", json={"url": "https://example.test/start"})

    assert response.status_code == 200
    payload = response.json()
    trial_id = UUID(payload.pop("trial_id"))
    assert payload == {
        "requested_url": "https://example.test/start",
        "final_url": "https://example.test/final",
        "title": "Preview title",
        "description": "Preview description",
        "site_name": "example.test",
        "image_data_url": None,
    }
    assert fetcher.requests == [
        FetchRequest(url="https://example.test/start", trial_id=trial_id)
    ]


def test_preview_fetches_raster_image_through_the_page_fetcher() -> None:
    class ImageFetcher:
        def __init__(self) -> None:
            self.requests: list[FetchRequest] = []

        def fetch(self, request: FetchRequest) -> FetchedPage:
            self.requests.append(request)
            if len(self.requests) == 1:
                return FetchedPage(
                    request.url,
                    "https://example.test/story",
                    200,
                    "text/html",
                    "93.184.216.34",
                    b'<meta property="og:site_name" content="Example News">'
                    b'<meta property="og:image" content="/cover.png">',
                )
            return FetchedPage(
                request.url,
                request.url,
                200,
                "image/png",
                "93.184.216.34",
                b"\x89PNG\r\n\x1a\nimage data",
            )

    fetcher = ImageFetcher()
    with TestClient(create_app(fetcher=fetcher)) as client:
        payload = client.post(
            "/preview", json={"url": "https://example.test/story"}
        ).json()

    assert payload["site_name"] == "Example News"
    assert payload["image_data_url"] == "data:image/png;base64,iVBORw0KGgppbWFnZSBkYXRh"
    assert [request.url for request in fetcher.requests] == [
        "https://example.test/story",
        "https://example.test/cover.png",
    ]


def test_open_graph_metadata_takes_precedence_over_twitter_cards() -> None:
    metadata = parse_html_metadata(
        b'<meta name="twitter:title" content="Twitter title">'
        b'<meta name="twitter:description" content="Twitter summary">'
        b'<meta name="twitter:image" content="/twitter.png">'
        b'<meta property="og:title" content="Open Graph title">'
        b'<meta property="og:description" content="Open Graph summary">'
        b'<meta property="og:image" content="/og.png">',
        "text/html; charset=utf-8",
    )

    assert metadata.title == "Open Graph title"
    assert metadata.description == "Open Graph summary"
    assert metadata.image_url == "/og.png"


def test_preview_does_not_embed_svg_images() -> None:
    class SVGFetcher:
        def fetch(self, request: FetchRequest) -> FetchedPage:
            if request.url.endswith("/cover.svg"):
                return FetchedPage(
                    request.url,
                    request.url,
                    200,
                    "image/svg+xml",
                    "93.184.216.34",
                    b"<svg xmlns='http://www.w3.org/2000/svg'/>",
                )
            return FetchedPage(
                request.url,
                request.url,
                200,
                "text/html",
                "93.184.216.34",
                b'<title>Article</title><meta property="og:image" '
                b'content="/cover.svg">',
            )

    with TestClient(create_app(fetcher=SVGFetcher())) as client:
        payload = client.post(
            "/preview", json={"url": "https://example.test/story"}
        ).json()

    assert payload["title"] == "Article"
    assert payload["image_data_url"] is None


def test_preview_fetching_is_disabled_by_default() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/preview", json={"url": "https://example.test"})

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "fetching_disabled"
    UUID(response.json()["detail"]["trial_id"])


def test_preview_error_returns_the_trial_id_used_by_the_fetcher() -> None:
    fetcher = _FailingFetcher()
    with TestClient(create_app(fetcher=fetcher)) as client:
        response = client.post("/preview", json={"url": "https://example.test"})

    assert response.status_code == 502
    assert fetcher.request is not None
    assert response.json()["detail"] == {
        "trial_id": str(fetcher.request.trial_id),
        "code": "preview_failed",
        "message": "The upstream request failed: controlled failure",
    }


def test_non_html_page_keeps_the_observed_http_path() -> None:
    url = "https://example.test/image.png"
    trace = FetchTrace(
        events=(FetchHop(0, url, 200, "93.184.216.34", None, None, 1.0),)
    )

    class NonHTMLFetcher:
        def fetch(self, request: FetchRequest) -> FetchedPage:
            return FetchedPage(
                request.url,
                request.url,
                200,
                "image/png",
                "93.184.216.34",
                b"\x89PNG\r\n\x1a\n",
                trace,
            )

    with pytest.raises(UnsupportedContentTypeError) as caught:
        PreviewService(NonHTMLFetcher()).create(url, trial_id=UUID(int=1))

    assert caught.value.trace == trace
