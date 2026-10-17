from typing import Self

from ssrf_link_preview_lab.fetching.models import FetchTrace


class FetchError(Exception):
    """Base class for expected failures while fetching an upstream page."""

    def __init__(self, *args: object) -> None:
        super().__init__(*args)
        self.trace = FetchTrace()

    def with_trace(self, trace: FetchTrace) -> Self:
        self.trace = trace
        return self


class FetchingDisabledError(FetchError):
    def __init__(self) -> None:
        super().__init__(
            "Network fetching is disabled; choose a lab fetch policy explicitly."
        )


class InvalidUrlError(FetchError):
    """Raised when a URL is outside the common HTTP(S) input contract."""


class InvalidRedirectUrlError(FetchError):
    def __init__(self, reason: str) -> None:
        super().__init__(
            f"The upstream server returned an invalid redirect URL: {reason}"
        )


class ResponseTooLargeError(FetchError):
    def __init__(self, limit: int) -> None:
        super().__init__(f"The upstream response exceeded the {limit}-byte limit.")


class FetchTimeoutError(FetchError):
    def __init__(self, timeout_seconds: float) -> None:
        super().__init__(
            f"The upstream request exceeded the {timeout_seconds:g}-second timeout."
        )


class TooManyRedirectsError(FetchError):
    def __init__(self, max_redirects: int) -> None:
        super().__init__(f"The upstream request exceeded {max_redirects} redirects.")


class MissingRedirectLocationError(FetchError):
    def __init__(self, status_code: int) -> None:
        super().__init__(
            f"The upstream server returned HTTP {status_code} without a Location header."
        )


class UpstreamHttpError(FetchError):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"The upstream server returned HTTP {status_code}.")


class TransportError(FetchError):
    def __init__(self, curl_code: int, message: str) -> None:
        self.curl_code = curl_code
        super().__init__(f"The upstream request failed: {message}")


class AddressBlockedError(FetchError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
