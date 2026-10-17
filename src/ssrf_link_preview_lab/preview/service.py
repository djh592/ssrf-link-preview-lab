from uuid import UUID

from ssrf_link_preview_lab.fetching.models import FetchedPage, FetchRequest
from ssrf_link_preview_lab.fetching.protocols import PageFetcher
from ssrf_link_preview_lab.preview.errors import UnsupportedContentTypeError
from ssrf_link_preview_lab.preview.models import Preview
from ssrf_link_preview_lab.preview.parser import parse_html_metadata

_HTML_CONTENT_TYPES = {"text/html", "application/xhtml+xml"}


class PreviewService:
    """Turn a fetched HTML page into preview metadata and retain its trace."""

    def __init__(self, fetcher: PageFetcher) -> None:
        self._fetcher = fetcher

    def create(self, url: str, *, trial_id: UUID) -> Preview:
        page = self._fetcher.fetch(FetchRequest(url=url, trial_id=trial_id))
        content_type = _require_html(page)
        metadata = parse_html_metadata(page.body, content_type)

        return Preview(
            trial_id=trial_id,
            requested_url=page.requested_url,
            final_url=page.final_url,
            title=metadata.title,
            description=metadata.description,
            trace=page.trace,
        )


def _require_html(page: FetchedPage) -> str:
    media_type = (page.content_type or "").partition(";")[0].strip().casefold()
    if media_type not in _HTML_CONTENT_TYPES:
        raise UnsupportedContentTypeError(page.content_type)
    return page.content_type or media_type
