"""Run the isolated redirect baseline from this checkout."""

from pathlib import Path

from ssrf_link_preview_lab.experiments.cli import run_redirect_baseline_cli

if __name__ == "__main__":
    raise SystemExit(run_redirect_baseline_cli(Path(__file__).resolve().parent.parent))
