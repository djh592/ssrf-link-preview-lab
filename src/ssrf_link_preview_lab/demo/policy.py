"""Apply experiment defenses without permitting requests to real private networks."""

from ipaddress import IPv4Address
from time import monotonic
from urllib.parse import urlsplit

from ssrf_link_preview_lab.demo.dns import DemoDNS
from ssrf_link_preview_lab.demo.models import Defense
from ssrf_link_preview_lab.fetching.errors import FetchTimeoutError
from ssrf_link_preview_lab.fetching.models import AddressBinding, AddressDecision


class DemoAddressPolicy:
    """Evaluate defense decisions and bind every permitted connection.

    The selected defense may allow the synthetic internal report. The fixed
    connection boundary never permits other non-global addresses. A second
    DNS query models an unbound client's connection-stage lookup; this build
    of libcurl requires the selected answer through CURLOPT_RESOLVE.
    """

    def __init__(
        self, defense: Defense, external_ip: str, internal_ip: str, dns: DemoDNS
    ) -> None:
        self._defense = defense
        self._external_ip = external_ip
        self._lab_ips = frozenset((external_ip, internal_ip))
        self._dns = dns

    def prepare(
        self, url: str, sequence: int, timeout_seconds: float
    ) -> tuple[tuple[AddressDecision, ...], AddressBinding | None]:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        if hostname is None:
            return (self._deny(sequence, url, (), "Missing hostname"),), None

        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        deadline = monotonic() + timeout_seconds
        check = self._defense in {Defense.EACH_HOP, Defense.BOUND} or (
            self._defense is Defense.INITIAL and sequence == 0
        )
        checked_ip = None
        decisions: list[AddressDecision] = []
        if check:
            checked_ip = self._dns.lookup(
                hostname, _remaining(deadline, timeout_seconds)
            )
            allowed = checked_ip == self._external_ip or _is_public(checked_ip)
            decision = AddressDecision(
                sequence,
                url,
                (checked_ip,),
                allowed,
                "Address check passed" if allowed else "Non-public address blocked",
                checked_ip if allowed else None,
                observed_at=monotonic(),
            )
            decisions.append(decision)
            if not allowed:
                return tuple(decisions), None

        connection_ip = (
            checked_ip
            if self._defense is Defense.BOUND and checked_ip is not None
            else self._dns.lookup(hostname, _remaining(deadline, timeout_seconds))
        )
        if not _permitted_connection(connection_ip, port, self._lab_ips):
            decisions.append(
                self._deny(
                    sequence,
                    url,
                    (connection_ip,),
                    "Connection outside public web and isolated lab",
                )
            )
            return tuple(decisions), None

        return tuple(decisions), AddressBinding(hostname, port, connection_ip)

    @staticmethod
    def _deny(
        sequence: int, url: str, addresses: tuple[str, ...], reason: str
    ) -> AddressDecision:
        return AddressDecision(
            sequence, url, addresses, False, reason, observed_at=monotonic()
        )


def _permitted_connection(address: str, port: int, lab_ips: frozenset[str]) -> bool:
    if address in lab_ips:
        return port == 8080
    return port in {80, 443} and _is_public(address)


def _is_public(address: str) -> bool:
    return IPv4Address(address).is_global


def _remaining(deadline: float, timeout_seconds: float) -> float:
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise FetchTimeoutError(timeout_seconds)
    return remaining
