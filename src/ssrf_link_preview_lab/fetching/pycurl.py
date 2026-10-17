from dataclasses import dataclass, field

import pycurl

from ssrf_link_preview_lab.fetching.errors import (
    FetchError,
    FetchTimeoutError,
    ResponseTooLargeError,
    TransportError,
)
from ssrf_link_preview_lab.fetching.models import TransportRequest, TransportResponse
from ssrf_link_preview_lab.tracing import TRIAL_ID_HEADER

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


@dataclass(slots=True)
class _ResponseHeaders:
    values: dict[str, str] = field(default_factory=dict)

    def write(self, line: bytes) -> int:
        decoded = line.decode("iso-8859-1")
        if decoded.startswith("HTTP/"):
            self.values.clear()
        elif ":" in decoded:
            name, value = decoded.split(":", maxsplit=1)
            self.values[name.strip().casefold()] = value.strip()
        return len(line)

    def get(self, name: str) -> str | None:
        return self.values.get(name.casefold())


class PycurlTransport:
    """Perform one HTTP(S) request without following redirects.

    A supplied address binding is passed to libcurl's RESOLVE option so the
    connection uses that IP while the original hostname remains in the URL.
    """

    def send(self, request: TransportRequest) -> TransportResponse:
        body = _LimitedBody(request.max_body_bytes)
        headers = _ResponseHeaders()
        curl = pycurl.Curl()

        try:
            self._configure(curl, request, body, headers)
            try:
                curl.perform()
            except pycurl.error as error:
                raise _translate_error(
                    error,
                    body_exceeded=body.exceeded,
                    timeout_seconds=request.timeout_seconds,
                    max_body_bytes=request.max_body_bytes,
                ) from error

            return TransportResponse(
                url=str(curl.getinfo(pycurl.EFFECTIVE_URL)),
                status_code=int(curl.getinfo(pycurl.RESPONSE_CODE)),
                content_type=_optional_string(curl.getinfo(pycurl.CONTENT_TYPE)),
                location=headers.get("location"),
                peer_ip=_optional_string(curl.getinfo(pycurl.PRIMARY_IP)),
                body=bytes(body.data),
            )
        finally:
            curl.close()

    def _configure(
        self,
        curl: pycurl.Curl,
        request: TransportRequest,
        body: _LimitedBody,
        headers: _ResponseHeaders,
    ) -> None:
        timeout_ms = max(1, round(request.timeout_seconds * 1_000))

        curl.setopt(pycurl.URL, request.url)
        curl.setopt(pycurl.WRITEFUNCTION, body.write)
        curl.setopt(pycurl.HEADERFUNCTION, headers.write)
        curl.setopt(pycurl.HTTPHEADER, [f"{TRIAL_ID_HEADER}: {request.trial_id}"])
        curl.setopt(pycurl.USERAGENT, "ssrf-link-preview-lab/0.1")
        curl.setopt(pycurl.ACCEPT_ENCODING, "")
        curl.setopt(pycurl.NOSIGNAL, 1)
        curl.setopt(pycurl.TIMEOUT_MS, timeout_ms)
        curl.setopt(pycurl.CONNECTTIMEOUT_MS, timeout_ms)
        curl.setopt(pycurl.MAXFILESIZE_LARGE, request.max_body_bytes)
        curl.setopt(pycurl.FOLLOWLOCATION, 0)
        curl.setopt(pycurl.PROTOCOLS, _HTTP_PROTOCOLS)
        curl.setopt(pycurl.IPRESOLVE, pycurl.IPRESOLVE_V4)
        curl.setopt(pycurl.SSL_VERIFYPEER, 1)
        curl.setopt(pycurl.SSL_VERIFYHOST, 2)

        if request.address_binding is not None:
            binding = request.address_binding
            curl.setopt(
                pycurl.RESOLVE,
                [f"{binding.hostname}:{binding.port}:{binding.address}"],
            )


def _translate_error(
    error: pycurl.error,
    *,
    body_exceeded: bool,
    timeout_seconds: float,
    max_body_bytes: int,
) -> FetchError:
    match error.args:
        case (int(error_code), str(message)):
            pass
        case (str(message),):
            return TransportError(-1, message)
        case _:
            return TransportError(-1, str(error))

    if body_exceeded or error_code == pycurl.E_FILESIZE_EXCEEDED:
        return ResponseTooLargeError(max_body_bytes)
    if error_code == pycurl.E_OPERATION_TIMEDOUT:
        return FetchTimeoutError(timeout_seconds)
    return TransportError(error_code, message)


def _optional_string(value: object) -> str | None:
    if value is None or value == "":
        return None
    return str(value)
