import json
from uuid import UUID

from fastapi.testclient import TestClient
from pytest import CaptureFixture, MonkeyPatch

from ssrf_link_preview_lab.lab import client as lab_client
from ssrf_link_preview_lab.lab.constants import INTERNAL_REPORT_MARKER
from ssrf_link_preview_lab.lab.external import app as external_app
from ssrf_link_preview_lab.lab.internal import app as internal_app
from ssrf_link_preview_lab.tracing import TRIAL_ID_HEADER

_TRIAL_ID = UUID("b14e1287-75a4-42c4-b304-07793af19b91")


def test_external_service_redirects_to_internal_report() -> None:
    with TestClient(external_app, follow_redirects=False) as client:
        response = client.get(
            "/redirect/internal",
            headers={TRIAL_ID_HEADER: str(_TRIAL_ID)},
        )

    assert response.status_code == 302
    assert response.headers["location"] == (
        f"http://internal-report:8080/report?source_trial_id={_TRIAL_ID}"
    )


def test_internal_service_records_access_and_returns_marker(
    capsys: CaptureFixture[str],
) -> None:
    with TestClient(internal_app) as client:
        response = client.get(
            f"/report?source_trial_id={_TRIAL_ID}",
            headers={TRIAL_ID_HEADER: str(_TRIAL_ID)},
        )

    event = json.loads(capsys.readouterr().out)
    assert event["event"] == "internal_report_access"
    assert event["trial_id"] == str(_TRIAL_ID)
    assert event["source_trial_id"] == str(_TRIAL_ID)
    assert event["trial_ids_match"] is True
    assert INTERNAL_REPORT_MARKER in response.text
    assert str(_TRIAL_ID) in response.text


def test_health_client_exits_unsuccessfully_when_service_is_unreachable(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    def unreachable(url: str, *, timeout_seconds: float) -> dict[str, object]:
        assert url == "http://service.test/health"
        assert timeout_seconds == 2
        return {"reachable": False, "status_code": None, "error": "unreachable"}

    monkeypatch.setattr(lab_client, "probe_url", unreachable)

    exit_code = lab_client.main(
        ["health", "http://service.test/health", "--timeout", "2"]
    )

    assert exit_code == 1
    assert json.loads(capsys.readouterr().out) == {
        "reachable": False,
        "status_code": None,
        "error": "unreachable",
    }
