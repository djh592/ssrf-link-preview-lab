from uuid import UUID

from ssrf_link_preview_lab.fetching.errors import AddressBlockedError
from ssrf_link_preview_lab.fetching.models import (
    AddressDecision,
    FetchedPage,
    FetchRequest,
    FetchTrace,
)
from ssrf_link_preview_lab.preview.service import PreviewService
from ssrf_link_preview_lab.trials.execution import execute_preview

_TRIAL_ID = UUID(int=42)
_URL = "http://example.test/page"


class _PageFetcher:
    def __init__(self) -> None:
        self.requests: list[FetchRequest] = []

    def fetch(self, request: FetchRequest) -> FetchedPage:
        self.requests.append(request)
        return FetchedPage(
            requested_url=request.url,
            final_url=request.url,
            status_code=200,
            content_type="text/html",
            peer_ip="192.0.2.1",
            body=(
                b'<title>Expected title</title><meta name="description" '
                b'content="Expected description"><meta property="og:image" '
                b'content="/image.png">'
            ),
        )


class _BlockedFetcher:
    def fetch(self, request: FetchRequest) -> FetchedPage:
        decision = AddressDecision(
            0, request.url, ("127.0.0.1",), False, "Non-public address blocked"
        )
        raise AddressBlockedError(decision.reason).with_trace(FetchTrace((decision,)))


def test_execution_measures_metadata_without_image_request() -> None:
    fetcher = _PageFetcher()

    execution = execute_preview(
        PreviewService(fetcher, fetch_images=False), _URL, trial_id=_TRIAL_ID
    )

    assert execution.ok
    assert execution.preview is not None
    assert execution.preview.title == "Expected title"
    assert execution.preview.description == "Expected description"
    assert execution.preview.image_data_url is None
    assert len(fetcher.requests) == 1
    assert execution.duration_seconds >= 0
    assert execution.to_dict()["image_trace"] == {"events": []}


def test_expected_block_is_an_outcome_with_its_trace() -> None:
    execution = execute_preview(
        PreviewService(_BlockedFetcher()), _URL, trial_id=_TRIAL_ID
    )

    assert not execution.ok
    assert execution.failure is not None
    assert execution.failure.type == "AddressBlockedError"
    assert execution.trace.address_decisions[0].allowed is False
    assert execution.to_dict()["failure"] == {
        "type": "AddressBlockedError",
        "message": "Non-public address blocked",
    }
