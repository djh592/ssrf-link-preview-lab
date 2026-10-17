from uuid import UUID

from fastapi.testclient import TestClient

from ssrf_link_preview_lab.api.app import create_app
from ssrf_link_preview_lab.fetching.errors import TransportError
from ssrf_link_preview_lab.fetching.models import FetchedPage, FetchRequest


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
    }
    assert fetcher.requests == [
        FetchRequest(url="https://example.test/start", trial_id=trial_id)
    ]


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
