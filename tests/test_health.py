from fastapi.testclient import TestClient

from ssrf_link_preview_lab.api.app import create_app


def test_health() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
