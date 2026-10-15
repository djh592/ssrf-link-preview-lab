from typing import Protocol

from ssrf_link_preview_lab.fetching.models import FetchedPage


class PageFetcher(Protocol):
    def fetch(self, url: str) -> FetchedPage: ...
