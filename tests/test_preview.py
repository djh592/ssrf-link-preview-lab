from fastapi.testclient import TestClient

from ssrf_link_preview_lab.api.app import create_app
from ssrf_link_preview_lab.fetching.models import FetchedPage


class _StubFetcher:
    def fetch(self, url: str) -> FetchedPage:
        return FetchedPage(
            requested_url=url,
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


def test_preview_returns_page_metadata() -> None:
    with TestClient(create_app(fetcher=_StubFetcher())) as client:
        response = client.post("/preview", json={"url": "https://example.test/start"})

    assert response.status_code == 200
    assert response.json() == {
        "requested_url": "https://example.test/start",
        "final_url": "https://example.test/final",
        "title": "Preview title",
        "description": "Preview description",
    }


def test_preview_fetching_is_disabled_by_default() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/preview", json={"url": "https://example.test"})

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "fetching_disabled"
