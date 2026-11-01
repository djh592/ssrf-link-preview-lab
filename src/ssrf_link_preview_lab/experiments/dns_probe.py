"""Collect one real DNS experiment with independent service observations."""

import argparse
import json
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from ssrf_link_preview_lab.experiments.compose import ComposeProject
from ssrf_link_preview_lab.experiments.event_models import (
    DNSAuthorityAnswer,
    InternalReportAccess,
    TrialEvent,
)
from ssrf_link_preview_lab.experiments.event_parser import (
    parse_fetch_trace,
    parse_trial_events,
)
from ssrf_link_preview_lab.experiments.results import write_json_atomic
from ssrf_link_preview_lab.fetching.models import FetchTrace
from ssrf_link_preview_lab.fetching.strategies import Defense


def run_dns_probe_cli(root: Path, argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Probe the isolated recursive DNS path"
    )
    parser.add_argument(
        "--mode", choices=("external", "internal", "rebind"), default="rebind"
    )
    parser.add_argument("--ttl", type=int, choices=(0, 1, 60), default=0)
    parser.add_argument("--cache", choices=("empty", "primed"), default="empty")
    parser.add_argument(
        "--defense",
        choices=(Defense.EACH_HOP, Defense.BOUND),
        type=Defense,
        default=Defense.EACH_HOP,
    )
    arguments = parser.parse_args(argv)
    if arguments.cache == "primed" and (
        arguments.mode != "rebind" or arguments.ttl == 0
    ):
        parser.error("A primed external answer requires rebinding with TTL 1 or 60")

    trial_id = uuid4()
    project = replace(
        ComposeProject.from_environment(root),
        overlays=("compose.measure.yaml", "compose.dns.yaml"),
    )
    with project.running_services():
        addresses = {}
        for service in ("external-page", "internal-report"):
            result = project.exec_module(
                "preview", "ssrf_link_preview_lab.lab.client", "resolve", service
            )
            address = json.loads(result.stdout)["address"]
            if not isinstance(address, str):
                raise TypeError(f"{service} did not resolve to an IPv4 address")
            addresses[service] = address
        project.exec_module(
            "dns-authority",
            "ssrf_link_preview_lab.lab.dns_control",
            addresses["external-page"],
            addresses["internal-report"],
        )

        log_since = (datetime.now(UTC) - timedelta(seconds=2)).isoformat()
        result = project.exec_module(
            "preview",
            "ssrf_link_preview_lab.experiments.dns_probe_worker",
            str(trial_id),
            "--mode",
            arguments.mode,
            "--ttl",
            str(arguments.ttl),
            "--cache",
            arguments.cache,
            "--defense",
            arguments.defense.value,
        )
        payload = json.loads(result.stdout)
        execution = payload["execution"]
        if execution["trial_id"] != str(trial_id):
            raise ValueError("DNS worker returned a different trial ID")
        hostname = payload["hostname"]
        authority_events = tuple(
            event
            for event in parse_trial_events(
                "dns-authority",
                project.logs("dns-authority", since=log_since),
                trial_id=trial_id,
            )
        )
        internal_events = parse_trial_events(
            "internal-report",
            project.logs("internal-report", since=log_since),
            trial_id=trial_id,
        )
        resolver_lines = [
            line
            for line in project.logs("resolver", since=log_since).splitlines()
            if hostname in line
        ]
        trace = parse_fetch_trace(execution.get("trace"))
        authority_answers = tuple(
            event
            for event in authority_events
            if isinstance(event.details, DNSAuthorityAnswer)
        )
        evidence_issues = verify_dns_evidence(
            trial_id=trial_id,
            hostname=hostname,
            external_ip=addresses["external-page"],
            internal_ip=addresses["internal-report"],
            trace=trace,
            authority_answers=authority_answers,
            resolver_lines=resolver_lines,
            internal_events=internal_events,
            preview_ok=execution["ok"],
        )
        record = {
            **payload,
            "trial_id": str(trial_id),
            "authority_events": [event.to_dict() for event in authority_events],
            "resolver_log": resolver_lines,
            "internal_events": [event.to_dict() for event in internal_events],
            "internal_access": any(
                isinstance(event.details, InternalReportAccess)
                for event in internal_events
            ),
            "probe_evidence_complete": not evidence_issues,
            "evidence_issues": evidence_issues,
        }
        output_dir = root / "results"
        output_dir.mkdir(parents=True, exist_ok=True)
        destination = output_dir / f"dns-probe-{trial_id}.json"
        write_json_atomic(record, destination)
    print(
        f"DNS probe: {payload['hostname']}\n"
        f"Checked IPs: {', '.join(trace.address_decisions[0].resolved_addresses) if trace and trace.address_decisions else 'none'}\n"
        f"Authority A answers: {', '.join(event.details.address for event in authority_answers if isinstance(event.details, DNSAuthorityAnswer))}\n"
        f"HTTP peer: {trace.hops[-1].peer_ip if trace and trace.hops else 'none'}\n"
        f"Preview: {'generated' if execution['ok'] else 'unavailable'}\n"
        f"Internal access: {'observed' if record['internal_access'] else 'not observed'}\n"
        f"Authority events: {len(authority_events)}; resolver lines: {len(resolver_lines)}\n"
        f"Evidence: {', '.join(evidence_issues) if evidence_issues else 'complete'}\n"
        f"Raw evidence: {destination}"
    )
    return 0 if not evidence_issues else 1


def verify_dns_evidence(
    *,
    trial_id: UUID,
    hostname: str,
    external_ip: str,
    internal_ip: str,
    trace: FetchTrace | None,
    authority_answers: tuple[TrialEvent, ...],
    resolver_lines: list[str],
    internal_events: tuple[TrialEvent, ...],
    preview_ok: bool,
) -> list[str]:
    """Report gaps in the observed authority-to-fetch chain."""
    issues: list[str] = []
    expected_url = f"http://{hostname}:8080/report"
    answers = tuple(
        event.details
        for event in authority_answers
        if isinstance(event.details, DNSAuthorityAnswer)
        and event.details.hostname == f"{hostname}."
    )
    if not answers:
        issues.append("no authority A answer for the trial hostname")
    elif any(answer.address not in {external_ip, internal_ip} for answer in answers):
        issues.append("authority returned an unexpected address")
    if not resolver_lines:
        issues.append("no resolver log for the trial hostname")
    if trace is None or not trace.address_decisions:
        issues.append("no recorded address check")
        return issues

    known_addresses = {answer.address for answer in answers}
    if any(
        decision.url != expected_url
        or not decision.resolved_addresses
        or any(
            address not in known_addresses for address in decision.resolved_addresses
        )
        for decision in trace.address_decisions
    ):
        issues.append("checked address has no matching authority answer")

    final_hop = trace.hops[-1] if trace.hops else None
    if preview_ok and final_hop is None:
        issues.append("successful preview has no HTTP response")
    elif final_hop is None and not any(
        not decision.allowed for decision in trace.address_decisions
    ):
        issues.append("no HTTP response or recorded address block")
    elif final_hop is not None:
        expected_service = {
            external_ip: "external-page",
            internal_ip: "internal-report",
        }.get(final_hop.peer_ip)
        if (
            final_hop.url != expected_url
            or final_hop.peer_ip not in known_addresses
            or (
                expected_service is None
                or final_hop.responder_service != expected_service
                or final_hop.responder_trial_id != str(trial_id)
            )
        ):
            issues.append("HTTP peer and service identity do not match DNS evidence")

    accessed_internal = any(
        isinstance(event.details, InternalReportAccess) for event in internal_events
    )
    if (
        final_hop is not None and final_hop.responder_service == "internal-report"
    ) != accessed_internal:
        issues.append("internal response and service log disagree")
    return issues
