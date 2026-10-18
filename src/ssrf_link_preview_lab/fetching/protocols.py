"""Contracts between fetching, address policy, and HTTP transport."""

from typing import Protocol

from ssrf_link_preview_lab.fetching.models import (
    AddressBinding,
    AddressDecision,
    FetchedPage,
    FetchRequest,
    TransportRequest,
    TransportResponse,
)


class HttpTransport(Protocol):
    """Send one HTTP request without following redirects or applying policy."""

    def send(self, request: TransportRequest) -> TransportResponse: ...


class PageFetcher(Protocol):
    """Fetch a page and return its request trace, or raise a fetch error."""

    def fetch(self, request: FetchRequest) -> FetchedPage: ...


class AddressPolicy(Protocol):
    """Decide whether a URL may be fetched and optionally bind its connection."""

    def prepare(
        self, url: str, sequence: int, timeout_seconds: float
    ) -> tuple[tuple[AddressDecision, ...], AddressBinding | None]:
        """Inspect one hop before transport sends it.

        Any denied decision prevents the request. A binding makes transport
        connect to that address while retaining the URL's hostname.
        """
        ...
