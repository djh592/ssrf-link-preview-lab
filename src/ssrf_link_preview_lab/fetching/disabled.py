from ssrf_link_preview_lab.fetching.errors import FetchingDisabledError
from ssrf_link_preview_lab.fetching.models import FetchedPage


class DisabledFetcher:
    def fetch(self, url: str) -> FetchedPage:
        raise FetchingDisabledError
