"""Entry point for one isolated recursive DNS experiment."""

from pathlib import Path

from ssrf_link_preview_lab.experiments.dns_probe import run_dns_probe_cli

if __name__ == "__main__":
    raise SystemExit(run_dns_probe_cli(Path(__file__).resolve().parent.parent))
