"""Entry point for bounded offline policy measurements."""

from pathlib import Path

from ssrf_link_preview_lab.experiments.measure_cli import run_measurements_cli

if __name__ == "__main__":
    raise SystemExit(run_measurements_cli(Path(__file__).resolve().parent.parent))
