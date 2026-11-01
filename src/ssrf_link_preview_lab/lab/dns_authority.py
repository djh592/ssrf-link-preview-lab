"""Controlled authoritative DNS service for isolated rebinding experiments."""

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import IPv4Address
from socketserver import BaseRequestHandler, ThreadingUDPServer
from threading import Lock, Thread
from uuid import UUID

import dns.exception
import dns.flags
import dns.message
import dns.rdataclass
import dns.rdatatype
import dns.rrset

from ssrf_link_preview_lab.tracing import write_structured_event

_NAME = re.compile(
    r"t([0-9a-f]{32})\.(external|internal|rebind)\.ttl(0|1|60)\.attack\.lab\."
)


class AuthorityState:
    """Map one trial-specific name to stable or changing IPv4 answers."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._external: str | None = None
        self._internal: str | None = None
        self._counts: dict[str, int] = {}

    def configure(self, external: str, internal: str) -> None:
        external_ip = str(IPv4Address(external))
        internal_ip = str(IPv4Address(internal))
        if external_ip == internal_ip:
            raise ValueError("External and internal services need different addresses")
        with self._lock:
            self._external = external_ip
            self._internal = internal_ip
            self._counts.clear()

    @property
    def configured(self) -> bool:
        with self._lock:
            return self._external is not None and self._internal is not None

    def answer(self, query: dns.message.Message) -> dns.message.Message:
        response = dns.message.make_response(query)
        response.flags |= dns.flags.AA
        for question in query.question:
            name = question.name.to_text().lower()
            matched = _NAME.fullmatch(name)
            if matched is None or question.rdclass != dns.rdataclass.IN:
                continue
            trial_id = UUID(hex=matched.group(1))
            if question.rdtype != dns.rdatatype.A:
                write_structured_event(
                    "dns_authority_query",
                    trial_id=trial_id,
                    hostname=name,
                    record_type=dns.rdatatype.to_text(question.rdtype),
                )
                continue
            mode, ttl_text = matched.group(2), matched.group(3)
            with self._lock:
                if self._external is None or self._internal is None:
                    continue
                ordinal = self._counts.get(name, 0) + 1
                self._counts[name] = ordinal
                address = (
                    self._internal
                    if mode == "internal" or (mode == "rebind" and ordinal > 1)
                    else self._external
                )
            ttl = int(ttl_text)
            response.answer.append(dns.rrset.from_text(name, ttl, "IN", "A", address))
            write_structured_event(
                "dns_authority_answer",
                trial_id=trial_id,
                hostname=name,
                address=address,
                ttl=ttl,
                query=ordinal,
            )
        return response


class _UDPServer(ThreadingUDPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, authority: AuthorityState) -> None:
        self.authority = authority
        super().__init__(("0.0.0.0", 5353), _DNSHandler)


class _DNSHandler(BaseRequestHandler):
    def handle(self) -> None:
        packet, socket = self.request
        server = self.server
        if not isinstance(server, _UDPServer) or not isinstance(packet, bytes):
            return
        try:
            response = server.authority.answer(dns.message.from_wire(packet))
            socket.sendto(response.to_wire(), self.client_address)
        except (ValueError, dns.exception.DNSException):
            return


class _ControlServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, authority: AuthorityState) -> None:
        self.authority = authority
        super().__init__(("127.0.0.1", 8053), _ControlHandler)


class _ControlHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/health":
            self.send_error(404)
            return
        server = self.server
        if isinstance(server, _ControlServer):
            self._respond(200, {"configured": server.authority.configured})

    def do_POST(self) -> None:
        if self.path != "/configure":
            self.send_error(404)
            return
        size = int(self.headers.get("Content-Length", "0"))
        if size not in range(1, 1025):
            self.send_error(400)
            return
        try:
            payload = json.loads(self.rfile.read(size))
            external = payload["external"]
            internal = payload["internal"]
            if not isinstance(external, str) or not isinstance(internal, str):
                raise TypeError("Both service addresses must be strings")
            server = self.server
            if not isinstance(server, _ControlServer):
                raise TypeError("Unexpected control server")
            server.authority.configure(external, internal)
        except (ValueError, TypeError, KeyError):
            self.send_error(400)
            return
        self._respond(200, {"configured": True})

    def _respond(self, status: int, payload: dict[str, bool]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


def main() -> None:
    authority = AuthorityState()
    dns_server = _UDPServer(authority)
    control_server = _ControlServer(authority)
    control_thread = Thread(target=control_server.serve_forever, daemon=True)
    control_thread.start()
    try:
        dns_server.serve_forever()
    finally:
        dns_server.server_close()
        control_server.shutdown()
        control_server.server_close()
        control_thread.join()


if __name__ == "__main__":
    main()
