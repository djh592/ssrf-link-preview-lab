"""Run the isolated redirect baseline with terminal or JSON output."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from ssrf_link_preview_lab.experiments.compose import ComposeProject
from ssrf_link_preview_lab.experiments.redirect_baseline import (
    REDIRECT_BASELINE_SPEC,
    ProgressReporter,
    run_redirect_baseline,
)
from ssrf_link_preview_lab.experiments.results import save_trial_run
from ssrf_link_preview_lab.experiments.runner import execute_trial
from ssrf_link_preview_lab.experiments.terminal import render_trial_run
from ssrf_link_preview_lab.experiments.trial_models import TrialResult


def run_redirect_baseline_cli(root: Path, argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the isolated redirect baseline")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    arguments = parser.parse_args(argv)

    reporter: ProgressReporter | None = None
    if arguments.format == "text":
        print("Running the controlled redirect baseline\n", flush=True)
        reporter = lambda message: print(f"[check] {message}", flush=True)

    run = execute_trial(
        REDIRECT_BASELINE_SPEC,
        lambda: _run_managed_trial(root, reporter),
    )
    result_path = save_trial_run(run, root / "results")
    if arguments.format == "json":
        print(json.dumps(run.to_dict(), indent=2, sort_keys=True))
        print(f"Raw result saved to {result_path}", file=sys.stderr)
    else:
        print(f"\n{render_trial_run(run)}")
        print(f"\nRaw result saved to {result_path}")
    return 0 if run.verification_passed else 1


def _run_managed_trial(root: Path, reporter: ProgressReporter | None) -> TrialResult:
    project = ComposeProject.from_environment(root)
    if reporter is not None:
        reporter("Validating and starting isolated services")
    with project.running_services():
        return run_redirect_baseline(project, report_progress=reporter)
