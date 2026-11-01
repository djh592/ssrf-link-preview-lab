from typing import Self

from ssrf_link_preview_lab.fetching.models import FetchTrace


class FetchError(Exception):
    """Base class for expected failures while fetching an upstream page."""

    def __init__(self, *args: object) -> None:
        super().__init__(*args)
        self.trace = FetchTrace()
        self.peer_ip: str | None = None
        self.status_code: int | None = None
        self.responder_service: str | None = None
        self.responder_trial_id: str | None = None

    def with_trace(self, trace: FetchTrace) -> Self:
        self.trace = trace
        return self

    def with_transport_observation(
        self,
        peer_ip: str | None,
        status_code: int | None,
        responder_service: str | None = None,
        responder_trial_id: str | None = None,
    ) -> Self:
        self.peer_ip = peer_ip
        self.status_code = status_code
        self.responder_service = responder_service
        self.responder_trial_id = responder_trial_id
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


class DNSLookupError(FetchError):
    def __init__(self, hostname: str, detail: str) -> None:
        super().__init__(f"DNS lookup failed for {hostname}: {detail}")


class TooManyRedirectsError(FetchError):
    def __init__(self, max_redirects: int) -> None:
        super().__init__(f"The upstream request exceeded {max_redirects} redirects.")


class RedirectDisallowedError(FetchError):
    def __init__(self, status_code: int) -> None:
        super().__init__(
            f"The upstream server returned HTTP {status_code}; redirects are disabled."
        )
        self.status_code = status_code


class MissingRedirectLocationError(FetchError):
    def __init__(self, status_code: int) -> None:
        super().__init__(
            f"The upstream server returned HTTP {status_code} without a Location header."
        )


class UpstreamHttpError(FetchError):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"The upstream server returned HTTP {status_code}.")
        self.status_code = status_code


class TransportError(FetchError):
    def __init__(self, curl_code: int, message: str) -> None:
        self.curl_code = curl_code
        super().__init__(f"The upstream request failed: {message}")


class AddressBlockedError(FetchError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
