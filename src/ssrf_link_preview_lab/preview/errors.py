from ssrf_link_preview_lab.fetching.models import FetchTrace


class UnsupportedContentTypeError(Exception):
    def __init__(self, content_type: str | None, trace: FetchTrace) -> None:
        self.trace = trace
        rendered_type = content_type or "missing Content-Type"
        super().__init__(f"The upstream response is not HTML ({rendered_type}).")
