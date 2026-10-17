"""Address checks and connection binding for the isolated lab hosts."""

import socket
from time import monotonic
from urllib.parse import urlsplit

from ssrf_link_preview_lab.demo.dns import DemoDNS
from ssrf_link_preview_lab.demo.models import Defense
from ssrf_link_preview_lab.fetching.models import AddressBinding, AddressDecision


class LabAddressPolicy:
    """Restrict all demo requests to lab hosts and model selected defenses.

    The allowlisted external IP represents the permitted zone in this lab; it
    is not a general-purpose public-address classification policy.
    """

    def __init__(self, defense: Defense, external_ip: str, dns: DemoDNS) -> None:
        self._defense = defense
        self._external_ip = external_ip
        self._dns = dns

    def prepare(
        self, url: str, sequence: int, timeout_seconds: float
    ) -> tuple[AddressDecision | None, AddressBinding | None]:
        """Check this hop and select its connection address when needed.

        The lab-host restriction always applies. For ``rebind.lab``, an
        unbound request makes a separate connection-stage DNS query; the
        checked-and-bound defense instead reuses the checked answer.
        """
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        if (
            parsed.scheme != "http"
            or parsed.port != 8080
            or host not in {"external-page", "internal-report", "rebind.lab"}
        ):
            decision = AddressDecision(
                sequence,
                url,
                (),
                False,
                "Outside the three isolated lab hosts",
                observed_at=monotonic(),
            )
            return decision, None

        check = self._defense in {Defense.EACH_HOP, Defense.BOUND} or (
            self._defense is Defense.INITIAL and sequence == 0
        )
        if host == "rebind.lab":
            checked_ip = self._dns.resolve(timeout_seconds) if check else None
        else:
            checked_ip = socket.gethostbyname(host) if check else None

        decision = None
        if checked_ip is not None:
            allowed = checked_ip == self._external_ip
            decision = AddressDecision(
                sequence,
                url,
                (checked_ip,),
                allowed,
                "Allowed external lab address"
                if allowed
                else "Internal lab address blocked",
                checked_ip if allowed else None,
                observed_at=monotonic(),
            )
            if not allowed:
                return decision, None

        binding = None
        if host == "rebind.lab":
            connection_ip = checked_ip
            if connection_ip is None or self._defense is not Defense.BOUND:
                connection_ip = self._dns.resolve(timeout_seconds)
            binding = AddressBinding(host, 8080, connection_ip)
        elif self._defense is Defense.BOUND and checked_ip is not None:
            binding = AddressBinding(host, 8080, checked_ip)
        return decision, binding
