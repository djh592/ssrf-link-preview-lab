"""Launch the browser demo with an isolated, instance-scoped Compose project."""

import sys
from os import environ
from pathlib import Path
from threading import Event

from ssrf_link_preview_lab.experiments.compose import (
    ComposeProject,
    ComposeProjectInUseError,
)


def run_browser_demo(root: Path) -> int:
    port = environ.get("SSRF_LAB_PORT", "8765")
    if not port.isdecimal() or not 1024 <= int(port) <= 65535:
        print("SSRF_LAB_PORT must be between 1024 and 65535.", file=sys.stderr)
        return 2
    if environ.get("SSRF_LAB_PUBLIC_EGRESS") != "1":
        print(
            "The browser demo has public network egress. Set "
            "SSRF_LAB_PUBLIC_EGRESS=1 only in an authorized personal environment.",
            file=sys.stderr,
        )
        return 2
    project = ComposeProject.from_environment(root)
    project = ComposeProject(
        root=project.root,
        instance=project.instance,
        overlays=("compose.demo.yaml", "compose.public.yaml"),
    )
    project.validate()
    existing = project.services(include_stopped=True)
    if existing:
        raise ComposeProjectInUseError(project.project_name, existing)

    print("Building the one shared image with Compose parallelism limited to 1...")
    project.run("build", "preview", timeout_seconds=600)
    with project.running_services():
        print(f"Browser demo: http://127.0.0.1:{port}")
        print("Press Ctrl+C to stop only this instance.")
        try:
            Event().wait()
        except KeyboardInterrupt:
            pass
    return 0
