import re
from ipaddress import IPv4Address, IPv6Address, ip_address
from urllib.parse import urlsplit

from ssrf_link_preview_lab.fetching.errors import InvalidUrlError

_HOST_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")


def validate_http_url(url: str) -> str:
    if any(ord(character) < 32 or ord(character) == 127 for character in url):
        raise InvalidUrlError("The URL cannot contain control characters.")

    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as error:
        raise InvalidUrlError("The URL is malformed.") from error

    if parsed.scheme.lower() not in {"http", "https"}:
        raise InvalidUrlError("Only HTTP and HTTPS URLs are supported.")
    if parsed.hostname is None:
        raise InvalidUrlError("The URL must include a hostname.")
    if parsed.username is not None or parsed.password is not None:
        raise InvalidUrlError("Credentials in URLs are not supported.")
    if port is not None and not 1 <= port <= 65_535:
        raise InvalidUrlError("The URL contains an invalid port.")

    try:
        address = ip_address(parsed.hostname)
    except ValueError:
        hostname = parsed.hostname
        if (
            not hostname.isascii()
            or len(hostname) > 253
            or not all(_HOST_LABEL.fullmatch(label) for label in hostname.split("."))
            or all(character in "0123456789." for character in hostname)
        ):
            raise InvalidUrlError(
                "The URL must use a canonical ASCII hostname."
            ) from None
    else:
        if isinstance(address, IPv6Address):
            raise InvalidUrlError("IPv6 URLs are outside this experiment's scope.")
        if isinstance(address, IPv4Address) and str(address) != parsed.hostname:
            raise InvalidUrlError("The URL must use a canonical IPv4 address.")

    return url
