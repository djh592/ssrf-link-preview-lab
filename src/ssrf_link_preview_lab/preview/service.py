from base64 import b64encode
from urllib.parse import urljoin, urlsplit
from uuid import UUID

from ssrf_link_preview_lab.fetching.errors import FetchError
from ssrf_link_preview_lab.fetching.models import FetchedPage, FetchRequest, FetchTrace
from ssrf_link_preview_lab.fetching.protocols import PageFetcher
from ssrf_link_preview_lab.preview.errors import UnsupportedContentTypeError
from ssrf_link_preview_lab.preview.models import Preview
from ssrf_link_preview_lab.preview.parser import parse_html_metadata

_HTML_CONTENT_TYPES = {"text/html", "application/xhtml+xml"}
_IMAGE_SIGNATURES = {
    "image/png": lambda body: body.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": lambda body: body.startswith(b"\xff\xd8\xff"),
    "image/webp": lambda body: body.startswith(b"RIFF") and body[8:12] == b"WEBP",
    "image/gif": lambda body: body.startswith((b"GIF87a", b"GIF89a")),
}


class PreviewService:
    """Turn a fetched HTML page into preview metadata and retain its trace."""

    def __init__(self, fetcher: PageFetcher) -> None:
        self._fetcher = fetcher

    def create(self, url: str, *, trial_id: UUID) -> Preview:
        page = self._fetcher.fetch(FetchRequest(url=url, trial_id=trial_id))
        content_type = _require_html(page)
        metadata = parse_html_metadata(page.body, content_type)
        image_data_url, image_trace = self._fetch_image(
            page.final_url, metadata.image_url, trial_id
        )

        return Preview(
            trial_id=trial_id,
            requested_url=page.requested_url,
            final_url=page.final_url,
            title=metadata.title,
            description=metadata.description,
            trace=page.trace,
            site_name=metadata.site_name or urlsplit(page.final_url).hostname,
            image_data_url=image_data_url,
            image_trace=image_trace,
        )

    def _fetch_image(
        self, page_url: str, image_url: str | None, trial_id: UUID
    ) -> tuple[str | None, FetchTrace]:
        if image_url is None or len(image_url) > 2_048:
            return None, FetchTrace()
        try:
            image = self._fetcher.fetch(
                FetchRequest(url=urljoin(page_url, image_url), trial_id=trial_id)
            )
        except FetchError as error:
            return None, error.trace
        except ValueError:
            return None, FetchTrace()

        media_type = (image.content_type or "").partition(";")[0].strip().casefold()
        signature = _IMAGE_SIGNATURES.get(media_type)
        if signature is None or not signature(image.body):
            return None, image.trace
        encoded = b64encode(image.body).decode("ascii")
        return f"data:{media_type};base64,{encoded}", image.trace


def _require_html(page: FetchedPage) -> str:
    media_type = (page.content_type or "").partition(";")[0].strip().casefold()
    if media_type not in _HTML_CONTENT_TYPES:
        raise UnsupportedContentTypeError(page.content_type, page.trace)
    return page.content_type or media_type
