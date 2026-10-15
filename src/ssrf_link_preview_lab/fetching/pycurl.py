from dataclasses import dataclass, field

import pycurl

from ssrf_link_preview_lab.fetching.errors import (
    FetchError,
    FetchTimeoutError,
    ResponseTooLargeError,
    TooManyRedirectsError,
    TransportError,
    UpstreamHttpError,
)
from ssrf_link_preview_lab.fetching.models import FetchedPage, FetchLimits
from ssrf_link_preview_lab.fetching.url import validate_http_url

_HTTP_PROTOCOLS = pycurl.PROTO_HTTP | pycurl.PROTO_HTTPS


@dataclass(slots=True)
class _LimitedBody:
    limit: int
    data: bytearray = field(default_factory=bytearray)
    exceeded: bool = False

    def write(self, chunk: bytes) -> int:
        if len(self.data) + len(chunk) > self.limit:
            self.exceeded = True
            return 0

        self.data.extend(chunk)
        return len(chunk)


class PycurlFetcher:
    def __init__(self, limits: FetchLimits | None = None) -> None:
        self._limits = limits or FetchLimits()

    def fetch(self, url: str) -> FetchedPage:
        validated_url = validate_http_url(url)
        body = _LimitedBody(self._limits.max_body_bytes)
        curl = pycurl.Curl()

        try:
            self._configure(curl, validated_url, body)
            try:
                curl.perform()
            except pycurl.error as error:
                raise self._translate_error(error, body.exceeded) from error

            status_code = int(curl.getinfo(pycurl.RESPONSE_CODE))
            if not 200 <= status_code < 300:
                raise UpstreamHttpError(status_code)

            return FetchedPage(
                requested_url=validated_url,
                final_url=str(curl.getinfo(pycurl.EFFECTIVE_URL)),
                status_code=status_code,
                content_type=_optional_string(curl.getinfo(pycurl.CONTENT_TYPE)),
                peer_ip=_optional_string(curl.getinfo(pycurl.PRIMARY_IP)),
                body=bytes(body.data),
            )
        finally:
            curl.close()

    def _configure(self, curl: pycurl.Curl, url: str, body: _LimitedBody) -> None:
        timeout_ms = round(self._limits.timeout_seconds * 1_000)

        curl.setopt(pycurl.URL, url)
        curl.setopt(pycurl.WRITEFUNCTION, body.write)
        curl.setopt(pycurl.USERAGENT, "ssrf-link-preview-lab/0.1")
        curl.setopt(pycurl.ACCEPT_ENCODING, "")
        curl.setopt(pycurl.NOSIGNAL, 1)
        curl.setopt(pycurl.TIMEOUT_MS, timeout_ms)
        curl.setopt(pycurl.CONNECTTIMEOUT_MS, timeout_ms)
        curl.setopt(pycurl.MAXFILESIZE_LARGE, self._limits.max_body_bytes)
        curl.setopt(pycurl.FOLLOWLOCATION, 1)
        curl.setopt(pycurl.MAXREDIRS, self._limits.max_redirects)
        curl.setopt(pycurl.PROTOCOLS, _HTTP_PROTOCOLS)
        curl.setopt(pycurl.REDIR_PROTOCOLS, _HTTP_PROTOCOLS)
        curl.setopt(pycurl.IPRESOLVE, pycurl.IPRESOLVE_V4)
        curl.setopt(pycurl.SSL_VERIFYPEER, 1)
        curl.setopt(pycurl.SSL_VERIFYHOST, 2)

    def _translate_error(self, error: pycurl.error, body_exceeded: bool) -> FetchError:
        match error.args:
            case (int(error_code), str(message)):
                pass
            case (str(message),):
                return TransportError(-1, message)

        if body_exceeded or error_code == pycurl.E_FILESIZE_EXCEEDED:
            return ResponseTooLargeError(self._limits.max_body_bytes)
        if error_code == pycurl.E_OPERATION_TIMEDOUT:
            return FetchTimeoutError(self._limits.timeout_seconds)
        if error_code == pycurl.E_TOO_MANY_REDIRECTS:
            return TooManyRedirectsError(self._limits.max_redirects)
        return TransportError(error_code, message)


def _optional_string(value: object) -> str | None:
    if value is None or value == "":
        return None
    return str(value)
