"""Serve trial-scoped DNS answers without exposing a DNS port to the host."""

from dataclasses import dataclass
from ipaddress import AddressValueError, IPv4Address
from socketserver import BaseRequestHandler, ThreadingUDPServer
from threading import Lock, Thread
from time import monotonic

import dns.exception
import dns.flags
import dns.message
import dns.query
import dns.rdataclass
import dns.rdatatype
import dns.resolver
import dns.rrset

from ssrf_link_preview_lab.fetching.errors import DNSLookupError


@dataclass(frozen=True, slots=True)
class DNSAnswer:
    query: int
    hostname: str
    address: str
    observed_at: float

    def to_dict(self) -> dict[str, object]:
        return {
            "query": self.query,
            "hostname": self.hostname,
            "address": self.address,
            "observed_at": self.observed_at,
        }


class _Server(ThreadingUDPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, authority: "DemoDNS") -> None:
        self.authority = authority
        super().__init__(("127.0.0.1", 0), _Handler)


class _Handler(BaseRequestHandler):
    def handle(self) -> None:
        packet, socket = self.request
        server = self.server
        if not isinstance(server, _Server) or not isinstance(packet, bytes):
            return
        try:
            query = dns.message.from_wire(packet)
            response = server.authority.answer(query)
            socket.sendto(response.to_wire(), self.client_address)
        except (ValueError, dns.exception.DNSException):
            return


class DemoDNS:
    """Answer ``rebind.lab`` queries on an ephemeral loopback UDP port.

    Rebinding changes the second and later answers for the current trial. The
    authority records each answer so the demo can show what it returned.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._external = ""
        self._internal = ""
        self._rebind = False
        self._answers: list[DNSAnswer] = []
        self._server = _Server(self)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def answers(self) -> tuple[DNSAnswer, ...]:
        with self._lock:
            return tuple(self._answers)

    def configure(self, external: str, internal: str, *, rebind: bool) -> None:
        """Start a trial with new addresses and clear its previous answers."""
        with self._lock:
            self._external = external
            self._internal = internal
            self._rebind = rebind
            self._answers.clear()

    def answer(self, query: dns.message.Message) -> dns.message.Message:
        response = dns.message.make_response(query)
        response.flags |= dns.flags.AA
        for question in query.question:
            if (
                question.name.to_text().lower() != "rebind.lab."
                or question.rdtype != dns.rdatatype.A
                or question.rdclass != dns.rdataclass.IN
            ):
                continue
            with self._lock:
                if not self._external:
                    continue
                count = len(self._answers) + 1
                address = (
                    self._internal if self._rebind and count > 1 else self._external
                )
                self._answers.append(
                    DNSAnswer(count, "rebind.lab", address, monotonic())
                )
            response.answer.append(
                dns.rrset.from_text("rebind.lab.", 0, "IN", "A", address)
            )
        return response

    def resolve(self, timeout_seconds: float) -> str:
        """Query this authority directly; do not use the system resolver."""
        query = dns.message.make_query("rebind.lab", dns.rdatatype.A)
        try:
            response = dns.query.udp(
                query,
                "127.0.0.1",
                port=self._server.server_address[1],
                timeout=min(timeout_seconds, 2.0),
            )
        except dns.exception.DNSException as error:
            raise DNSLookupError("rebind.lab", str(error)) from error
        for answer in response.answer:
            if answer.rdtype == dns.rdatatype.A:
                return answer[0].to_text()
        raise DNSLookupError("rebind.lab", "the authority returned no IPv4 address")

    def lookup(self, hostname: str, timeout_seconds: float) -> str:
        """Resolve ordinary hosts normally and the controlled zone locally."""
        try:
            return str(IPv4Address(hostname))
        except AddressValueError:
            pass
        if hostname == "rebind.lab":
            return self.resolve(timeout_seconds)
        try:
            answers = dns.resolver.resolve(
                hostname, "A", lifetime=min(timeout_seconds, 2.0)
            )
        except dns.exception.DNSException as error:
            raise DNSLookupError(hostname, str(error)) from error
        return answers[0].to_text()

    def close(self) -> None:
        """Stop the UDP server and wait for its thread to exit."""
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()
