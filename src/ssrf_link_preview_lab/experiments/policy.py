"""Address checks for offline experiments with genuine client-side DNS lookup."""

from ipaddress import IPv4Address
from time import monotonic
from typing import Protocol
from urllib.parse import urlsplit

import dns.exception
import dns.resolver

from ssrf_link_preview_lab.fetching.errors import DNSLookupError
from ssrf_link_preview_lab.fetching.models import AddressBinding, AddressDecision
from ssrf_link_preview_lab.fetching.strategies import Defense


class AddressResolver(Protocol):
    def resolve(self, hostname: str, timeout_seconds: float) -> tuple[str, ...]: ...


class RecursiveResolver:
    """Use the container resolver configuration for validation lookups."""

    def resolve(self, hostname: str, timeout_seconds: float) -> tuple[str, ...]:
        try:
            return (str(IPv4Address(hostname)),)
        except ValueError:
            pass
        try:
            answers = dns.resolver.resolve(hostname, "A", lifetime=timeout_seconds)
        except dns.exception.DNSException as error:
            raise DNSLookupError(hostname, str(error)) from error
        addresses = tuple(answer.to_text() for answer in answers)
        if not addresses:
            raise DNSLookupError(hostname, "the resolver returned no IPv4 address")
        return addresses


class LabAddressPolicy:
    """Check A records while leaving unbound connections to libcurl's resolver.

    The external lab service is an explicit exception to global-IP checks
    because Docker assigns it a private address. This policy is only for the
    offline testbed; it has no public-egress safety boundary.
    """

    def __init__(
        self,
        defense: Defense,
        external_ip: str,
        resolver: AddressResolver | None = None,
    ) -> None:
        self._defense = defense
        self._external_ip = external_ip
        self._resolver = resolver if resolver is not None else RecursiveResolver()

    def prepare(
        self, url: str, sequence: int, timeout_seconds: float
    ) -> tuple[tuple[AddressDecision, ...], AddressBinding | None]:
        if self._defense is Defense.NONE or (
            self._defense is Defense.INITIAL and sequence > 0
        ):
            return (), None

        parsed = urlsplit(url)
        hostname = parsed.hostname
        if hostname is None:
            raise DNSLookupError(url, "the URL has no hostname")
        addresses = self._resolver.resolve(hostname, timeout_seconds)
        allowed = all(
            address == self._external_ip or IPv4Address(address).is_global
            for address in addresses
        )
        selected = addresses[0] if allowed else None
        decision = AddressDecision(
            sequence=sequence,
            url=url,
            resolved_addresses=addresses,
            allowed=allowed,
            reason=(
                "All resolved addresses passed the check"
                if allowed
                else "A non-public address was blocked"
            ),
            selected_address=selected,
            observed_at=monotonic(),
        )
        if not allowed or self._defense not in {
            Defense.BOUND,
            Defense.NO_REDIRECTS,
        }:
            return (decision,), None
        assert selected is not None
        return (
            (decision,),
            AddressBinding(
                hostname=hostname,
                port=parsed.port or (443 if parsed.scheme == "https" else 80),
                address=selected,
            ),
        )
