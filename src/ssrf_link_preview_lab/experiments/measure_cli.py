"""Run bounded, sequential measurements in one isolated Compose instance."""

import argparse
import json
import os
import random
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from ssrf_link_preview_lab.experiments.compose import ComposeProject
from ssrf_link_preview_lab.experiments.measurements import Measurement, measure_once
from ssrf_link_preview_lab.experiments.results import write_json_atomic
from ssrf_link_preview_lab.experiments.scenarios import Scenario, case_for
from ssrf_link_preview_lab.experiments.summary import summarize
from ssrf_link_preview_lab.fetching.strategies import Defense


def run_measurements_cli(root: Path, argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure isolated link-preview policies"
    )
    parser.add_argument(
        "--scenario", action="append", type=Scenario, choices=list(Scenario)
    )
    parser.add_argument(
        "--defense", action="append", type=Defense, choices=list(Defense)
    )
    parser.add_argument("--repetitions", type=int, required=True)
    parser.add_argument("--max-trials", type=int, default=100)
    parser.add_argument("--seed", type=int, default=7508)
    parser.add_argument("--output", type=Path, default=root / "results")
    arguments = parser.parse_args(argv)
    scenarios = tuple(dict.fromkeys(arguments.scenario or list(Scenario)))
    defenses = tuple(dict.fromkeys(arguments.defense or list(Defense)))
    count = len(scenarios) * len(defenses) * arguments.repetitions
    if arguments.repetitions not in range(1, 101):
        parser.error("--repetitions must be between 1 and 100")
    if arguments.max_trials not in range(1, 1001) or count > arguments.max_trials:
        parser.error(
            f"Requested {count} trials; --max-trials must explicitly permit this count (up to 1000)"
        )

    project = replace(
        ComposeProject.from_environment(root), overlays=("compose.measure.yaml",)
    )
    records: list[Measurement] = []
    interrupted = False
    run_id = f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}_{uuid4().hex[:8]}"
    output_dir = arguments.output / run_id
    randomizer = random.Random(arguments.seed)

    with project.running_services():
        address_result = project.exec_module(
            "preview", "ssrf_link_preview_lab.lab.client", "resolve", "internal-report"
        )
        internal_ip = json.loads(address_result.stdout)["address"]
        if not isinstance(internal_ip, str):
            raise TypeError("Internal service did not resolve to an IPv4 address")
        cases = [case_for(scenario, internal_ip=internal_ip) for scenario in scenarios]
        output_dir.mkdir(parents=True, exist_ok=False)
        with (output_dir / "trials.jsonl").open("x", encoding="utf-8") as output:
            try:
                for repetition in range(arguments.repetitions):
                    conditions = [
                        (case, defense) for case in cases for defense in defenses
                    ]
                    randomizer.shuffle(conditions)
                    for case, defense in conditions:
                        record = measure_once(project, case, defense, repetition + 1)
                        output.write(
                            json.dumps(record.to_dict(), sort_keys=True) + "\n"
                        )
                        output.flush()
                        os.fsync(output.fileno())
                        records.append(record)
                        print(
                            f"[{len(records)}/{count}] {case.name.value} / {defense.value}: "
                            f"{'ERROR' if record.error else 'recorded'}",
                            flush=True,
                        )
            except KeyboardInterrupt:
                interrupted = True

    summary = {
        "requested_trials": count,
        "completed_trials": len(records),
        "interrupted": interrupted,
        "seed": arguments.seed,
        "conditions": summarize(records),
    }
    write_json_atomic(summary, output_dir / "summary.json")
    print(f"Results saved to {output_dir}")
    return 130 if interrupted else 1 if any(record.error for record in records) else 0
