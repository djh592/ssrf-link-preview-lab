from time import monotonic
from urllib.parse import urljoin

from ssrf_link_preview_lab.fetching.errors import (
    AddressBlockedError,
    FetchError,
    FetchTimeoutError,
    InvalidRedirectUrlError,
    InvalidUrlError,
    MissingRedirectLocationError,
    TooManyRedirectsError,
    UpstreamHttpError,
)
from ssrf_link_preview_lab.fetching.models import (
    AddressDecision,
    FetchedPage,
    FetchHop,
    FetchLimits,
    FetchRequest,
    FetchTrace,
    TransportRequest,
)
from ssrf_link_preview_lab.fetching.protocols import AddressPolicy, HttpTransport
from ssrf_link_preview_lab.fetching.pycurl import PycurlTransport
from ssrf_link_preview_lab.fetching.url import validate_http_url

_REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}


class RedirectingFetcher:
    """Follow bounded redirects and check each hop when a policy is supplied.

    Without a policy, this fetcher performs no address filtering. It is only
    suitable for the isolated baseline, not an exposed preview endpoint.
    """

    def __init__(
        self,
        transport: HttpTransport | None = None,
        limits: FetchLimits | None = None,
        address_policy: AddressPolicy | None = None,
    ) -> None:
        self._transport = transport if transport is not None else PycurlTransport()
        self._limits = limits if limits is not None else FetchLimits()
        self._address_policy = address_policy

    def fetch(self, request: FetchRequest) -> FetchedPage:
        """Return the final successful page or raise a fetch error with its trace."""
        requested_url = validate_http_url(request.url)
        current_url = requested_url
        deadline = monotonic() + self._limits.timeout_seconds
        hops: list[FetchHop] = []
        decisions: list[AddressDecision] = []

        try:
            while True:
                timeout_seconds = deadline - monotonic()
                if timeout_seconds <= 0:
                    raise FetchTimeoutError(self._limits.timeout_seconds)

                binding = None
                if self._address_policy is not None:
                    decision, binding = self._address_policy.prepare(
                        current_url, len(hops), timeout_seconds
                    )
                    if decision is not None:
                        decisions.append(decision)
                        if not decision.allowed:
                            raise AddressBlockedError(decision.reason)

                response = self._transport.send(
                    TransportRequest(
                        url=current_url,
                        trial_id=request.trial_id,
                        timeout_seconds=timeout_seconds,
                        max_body_bytes=self._limits.max_body_bytes,
                        address_binding=binding,
                    )
                )
                redirect_url = _resolve_redirect_url(
                    current_url,
                    status_code=response.status_code,
                    location=response.location,
                )

                hops.append(
                    FetchHop(
                        sequence=len(hops),
                        url=current_url,
                        status_code=response.status_code,
                        peer_ip=response.peer_ip,
                        location=response.location,
                        redirect_url=redirect_url,
                        observed_at=monotonic(),
                    )
                )

                if response.status_code in _REDIRECT_STATUS_CODES:
                    if redirect_url is None:
                        raise MissingRedirectLocationError(response.status_code)
                    if len(hops) > self._limits.max_redirects:
                        raise TooManyRedirectsError(self._limits.max_redirects)
                    try:
                        current_url = validate_http_url(redirect_url)
                    except InvalidUrlError as error:
                        raise InvalidRedirectUrlError(str(error)) from error
                    continue

                if not 200 <= response.status_code < 300:
                    raise UpstreamHttpError(response.status_code)

                return FetchedPage(
                    requested_url=requested_url,
                    final_url=response.url,
                    status_code=response.status_code,
                    content_type=response.content_type,
                    peer_ip=response.peer_ip,
                    body=response.body,
                    trace=FetchTrace(
                        hops=tuple(hops), address_decisions=tuple(decisions)
                    ),
                )
        except FetchError as error:
            raise error.with_trace(
                FetchTrace(hops=tuple(hops), address_decisions=tuple(decisions))
            )


def _resolve_redirect_url(
    current_url: str,
    *,
    status_code: int,
    location: str | None,
) -> str | None:
    if status_code not in _REDIRECT_STATUS_CODES or location is None:
        return None
    try:
        return urljoin(current_url, location)
    except ValueError:
        # Keep the target for the trace; the caller reports it as an invalid
        # redirect URL during validation.
        return location
