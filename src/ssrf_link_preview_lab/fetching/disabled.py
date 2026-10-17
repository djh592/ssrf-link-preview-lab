from ssrf_link_preview_lab.fetching.errors import FetchingDisabledError
from ssrf_link_preview_lab.fetching.models import FetchedPage, FetchRequest


class DisabledFetcher:
    def fetch(self, request: FetchRequest) -> FetchedPage:
        raise FetchingDisabledError
