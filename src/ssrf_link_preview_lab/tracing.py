import json
from datetime import UTC, datetime
from uuid import UUID

TRIAL_ID_HEADER = "X-SSRF-Lab-Trial-ID"
RESPONDER_SERVICE_HEADER = "X-SSRF-Lab-Service"
RESPONDER_TRIAL_HEADER = "X-SSRF-Lab-Observed-Trial-ID"


def write_structured_event(
    event: str,
    *,
    trial_id: UUID | str | None,
    **fields: object,
) -> None:
    record: dict[str, object] = {
        "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
        "event": event,
        "trial_id": str(trial_id) if trial_id is not None else None,
        **fields,
    }
    print(json.dumps(record, sort_keys=True), flush=True)
