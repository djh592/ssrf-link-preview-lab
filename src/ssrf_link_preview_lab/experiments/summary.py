"""Compute report metrics from saved per-attempt measurements."""

from collections import Counter, defaultdict
from math import ceil
from statistics import median

from ssrf_link_preview_lab.experiments.measurements import Measurement


def summarize(measurements: list[Measurement]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str], list[Measurement]] = defaultdict(list)
    for record in measurements:
        groups[(record.scenario.value, record.defense.value)].append(record)

    summaries: list[dict[str, object]] = []
    for (scenario, defense), records in sorted(groups.items()):
        known = [record for record in records if record.error is None]
        successful_normals = [
            record.duration_seconds
            for record in known
            if record.normal_success is True and record.duration_seconds is not None
        ]
        successful_normals.sort()
        failures = Counter(
            _failure_reason(record)
            for record in known
            if record.normal_success is False
            or (record.preview is not None and record.preview.get("ok") is False)
        )
        complete = len(known) == len(records)
        accesses = sum(record.internal_access is True for record in known)
        disclosures = sum(record.marker_disclosed is True for record in known)
        normal_successes = sum(record.normal_success is True for record in known)
        summaries.append(
            {
                "scenario": scenario,
                "defense": defense,
                "kind": records[0].kind,
                "attempted": len(records),
                "evidence_complete": len(known),
                "unresolved_trials": len(records) - len(known),
                "internal_accesses": accesses,
                "disclosures": disclosures,
                "normal_successes": normal_successes,
                "attack_rate": accesses / len(records)
                if complete and records[0].kind == "attack"
                else None,
                "disclosure_rate": disclosures / len(records)
                if complete and records[0].kind == "attack"
                else None,
                "normal_success_rate": normal_successes / len(records)
                if complete and records[0].kind == "normal"
                else None,
                "latency_median_seconds": (
                    median(successful_normals) if successful_normals else None
                ),
                "latency_p95_seconds": (
                    successful_normals[ceil(0.95 * len(successful_normals)) - 1]
                    if successful_normals
                    else None
                ),
                "preview_failures": dict(sorted(failures.items())),
            }
        )
    return summaries


def _failure_reason(record: Measurement) -> str:
    if record.preview is None:
        return "missing_preview"
    if record.preview.get("ok") is True:
        if record.duration_seconds is not None and record.duration_seconds > 10.0:
            return "task_timeout"
        return "metadata_mismatch"
    failure = record.preview.get("failure")
    if isinstance(failure, dict):
        kind = failure.get("type")
        if isinstance(kind, str):
            return kind
    return "unknown_preview_failure"
