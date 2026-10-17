"""Run the browser demonstration from this checkout."""

from pathlib import Path

from ssrf_link_preview_lab.demo.cli import run_browser_demo

if __name__ == "__main__":
    raise SystemExit(run_browser_demo(Path(__file__).resolve().parent.parent))
