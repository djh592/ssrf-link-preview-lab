import json
from datetime import UTC, datetime
from subprocess import CompletedProcess
from uuid import UUID

from ssrf_link_preview_lab.experiments.measurements import Measurement, measure_once
from ssrf_link_preview_lab.experiments.scenarios import Scenario, case_for
from ssrf_link_preview_lab.experiments.summary import summarize
from ssrf_link_preview_lab.fetching.strategies import Defense
from ssrf_link_preview_lab.lab.constants import INTERNAL_REPORT_MARKER


class _Project:
    def __init__(
        self,
        *,
        reached: bool,
        success: bool,
        response_service: str | None = None,
        omit_trace: bool = False,
        attempted_internal: bool = False,
    ) -> None:
        self.reached = reached
        self.success = success
        self.response_service = response_service
        self.omit_trace = omit_trace
        self.attempted_internal = attempted_internal
        self.trial_id: UUID | None = None

    def exec_module(
        self, service: str, module: str, *arguments: str, check: bool = True
    ) -> CompletedProcess[str]:
        assert service == "preview"
        assert module == "ssrf_link_preview_lab.experiments.worker"
        self.trial_id = UUID(arguments[-1])
        case = case_for(Scenario(arguments[0]), internal_ip="10.0.0.2")
        responder = self.response_service or (
            "external-page" if self.success and case.kind == "normal" else None
        )
        events = (
            [
                {
                    "type": "http_response",
                    "sequence": 0,
                    "url": case.target_url,
                    "status_code": 200,
                    "peer_ip": "10.0.0.2",
                    "location": None,
                    "redirect_url": None,
                    "responder_service": responder,
                    "responder_trial_id": str(self.trial_id),
                }
            ]
            if self.success
            else (
                [
                    {
                        "type": "connection_attempt",
                        "sequence": 0,
                        "url": case.target_url,
                        "selected_address": None,
                        "observed_at": 1.0,
                    }
                ]
                if self.attempted_internal
                else [
                    {
                        "type": "address_decision",
                        "sequence": 0,
                        "url": case.target_url,
                        "resolved_addresses": ["10.0.0.2"],
                        "allowed": False,
                        "reason": "A non-public address was blocked",
                        "selected_address": None,
                    }
                ]
            )
        )
        payload = {
            "trial_id": str(self.trial_id),
            "requested_url": case.target_url,
            "ok": self.success,
            "duration_seconds": 0.05,
            "trace": {"events": [] if self.omit_trace else events},
            "title": "Field Notes: An external page" if self.success else None,
            "description": (
                INTERNAL_REPORT_MARKER
                if self.response_service is not None
                else "A short field note from the controlled external site."
            )
            if self.success
            else None,
            "failure": None if self.success else {"type": "AddressBlockedError"},
        }
        return CompletedProcess([], 0, stdout=json.dumps(payload))

    def logs(self, service: str, *, since: str | None = None) -> str:
        assert service in {"external-page", "internal-report"}
        assert since is not None
        if service != "internal-report" or not self.reached or self.trial_id is None:
            return ""
        return json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "event": "internal_report_access",
                "trial_id": str(self.trial_id),
                "source_trial_id": None,
                "trial_ids_match": False,
            }
        )


def test_measurement_uses_internal_service_log_for_access() -> None:
    project = _Project(reached=True, success=False)
    case = case_for(Scenario.DIRECT_INTERNAL_IP, internal_ip="10.0.0.2")

    record = measure_once(project, case, Defense.INITIAL, 1)

    assert record.internal_access is True
    assert record.marker_disclosed is False
    assert record.normal_success is None
    assert record.duration_seconds == 0.05


def test_summary_separates_unknown_evidence_from_protection() -> None:
    case = case_for(Scenario.REDIRECT_INTERNAL, internal_ip="10.0.0.2")
    observed = measure_once(
        _Project(reached=True, success=False),
        case,
        Defense.EACH_HOP,
        1,
    )
    unknown = Measurement(
        case.name,
        Defense.EACH_HOP,
        2,
        UUID(int=1),
        "attack",
        case.target_url,
        None,
        None,
        None,
        None,
        None,
        "Docker logs unavailable",
    )

    (result,) = summarize([observed, unknown])

    assert result["attempted"] == 2
    assert result["internal_accesses"] == 1
    assert result["unresolved_trials"] == 1
    assert result["attack_rate"] is None


def test_normal_success_uses_expected_metadata_and_preview_latency() -> None:
    case = case_for(Scenario.NORMAL_PAGE, internal_ip="10.0.0.2")
    record = measure_once(
        _Project(reached=False, success=True),
        case,
        Defense.BOUND,
        1,
    )

    assert record.normal_success is True
    assert record.duration_seconds == 0.05
    (result,) = summarize([record])
    assert result["normal_success_rate"] == 1.0
    assert result["latency_median_seconds"] == 0.05
    assert result["latency_p95_seconds"] == 0.05


def test_marker_requires_matching_internal_response_identity() -> None:
    case = case_for(Scenario.DIRECT_INTERNAL_IP, internal_ip="10.0.0.2")
    claimed_external = measure_once(
        _Project(reached=False, success=True, response_service="external-page"),
        case,
        Defense.NONE,
        1,
    )
    confirmed_internal = measure_once(
        _Project(reached=True, success=True, response_service="internal-report"),
        case,
        Defense.NONE,
        2,
    )

    assert claimed_external.marker_disclosed is False
    assert confirmed_internal.marker_disclosed is True
    assert confirmed_internal.internal_access is True


def test_internal_response_without_service_event_is_not_a_protection_result() -> None:
    case = case_for(Scenario.DIRECT_INTERNAL_IP, internal_ip="10.0.0.2")
    record = measure_once(
        _Project(reached=False, success=True, response_service="internal-report"),
        case,
        Defense.NONE,
        1,
    )

    assert record.error == "Internal response identity and service log disagree"
    assert record.internal_access is None
    assert record.marker_disclosed is None
    assert summarize([record])[0]["attack_rate"] is None


def test_incomplete_worker_trace_is_not_a_protection_result() -> None:
    case = case_for(Scenario.DIRECT_INTERNAL_IP, internal_ip="10.0.0.2")
    record = measure_once(
        _Project(reached=False, success=False, omit_trace=True),
        case,
        Defense.EACH_HOP,
        1,
    )

    assert record.error == "Worker returned an incomplete fetch trace"
    assert record.internal_access is None
    assert summarize([record])[0]["attack_rate"] is None


def test_unlogged_internal_connection_attempt_is_unknown() -> None:
    case = case_for(Scenario.DIRECT_INTERNAL_IP, internal_ip="10.0.0.2")
    record = measure_once(
        _Project(reached=False, success=False, attempted_internal=True),
        case,
        Defense.NONE,
        1,
    )

    assert record.error == "Internal connection attempt has no matching service log"
    assert record.internal_access is None
    assert summarize([record])[0]["attack_rate"] is None
