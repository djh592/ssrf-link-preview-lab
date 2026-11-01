import json
import os
import re
import tempfile
from pathlib import Path
from uuid import uuid4

from ssrf_link_preview_lab.experiments.trial_models import TrialRun


def save_trial_run(run: TrialRun, directory: Path) -> Path:
    """Atomically save a trial record without leaving a partial result file."""
    timestamp = run.started_at.strftime("%Y%m%dT%H%M%S%fZ")
    identifier = run.result.trial_id if run.result is not None else uuid4()
    scenario = re.sub(r"[^a-z0-9]+", "-", run.spec.scenario.lower()).strip("-")
    destination = directory / f"{timestamp}_{scenario}_{identifier}.json"
    write_json_atomic(run.to_dict(), destination)
    return destination


def write_json_atomic(record: dict[str, object], destination: Path) -> None:
    """Replace one JSON artifact only after its complete contents are durable."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(record, indent=2, sort_keys=True) + "\n"

    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        temporary_path.replace(destination)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
