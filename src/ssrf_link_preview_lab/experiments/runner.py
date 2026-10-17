from collections.abc import Callable
from datetime import UTC, datetime
from time import monotonic

from ssrf_link_preview_lab.experiments.trial_models import (
    ExecutionStatus,
    TrialError,
    TrialResult,
    TrialRun,
    TrialSpec,
)

TrialOperation = Callable[[], TrialResult]


def execute_trial(spec: TrialSpec, operation: TrialOperation) -> TrialRun:
    """Capture a trial result or operational failure with elapsed time.

    Expected experiment outcomes belong in ``TrialResult``. Unexpected
    execution failures become ``TrialRun`` errors so callers can persist them.
    """
    started_at = datetime.now(UTC)
    started = monotonic()
    try:
        result = operation()
        if result.spec != spec:
            raise ValueError("Trial operation returned a result for a different spec")
    except Exception as error:  # noqa: BLE001
        return TrialRun(
            spec=spec,
            status=ExecutionStatus.ERROR,
            started_at=started_at,
            duration_seconds=monotonic() - started,
            error=TrialError.from_exception(error),
        )

    return TrialRun(
        spec=spec,
        status=ExecutionStatus.COMPLETED,
        started_at=started_at,
        duration_seconds=monotonic() - started,
        result=result,
    )
