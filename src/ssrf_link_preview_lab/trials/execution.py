"""Record one preview attempt independently of its presentation or evidence source."""

from dataclasses import dataclass, field
from time import monotonic
from uuid import UUID

from ssrf_link_preview_lab.fetching.errors import FetchError
from ssrf_link_preview_lab.fetching.models import FetchTrace
from ssrf_link_preview_lab.preview.errors import UnsupportedContentTypeError
from ssrf_link_preview_lab.preview.models import Preview
from ssrf_link_preview_lab.preview.service import PreviewService


@dataclass(frozen=True, slots=True)
class TrialFailure:
    type: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"type": self.type, "message": self.message}


@dataclass(frozen=True, slots=True)
class TrialExecution:
    """The fetch outcome and its trace, before independent evidence is assessed."""

    trial_id: UUID
    requested_url: str
    duration_seconds: float
    preview: Preview | None = None
    failure: TrialFailure | None = None
    trace: FetchTrace = field(default_factory=FetchTrace)

    def __post_init__(self) -> None:
        if (self.preview is None) == (self.failure is None):
            raise ValueError("A trial requires exactly one preview or failure")
        if self.duration_seconds < 0:
            raise ValueError("Trial duration cannot be negative")
        if self.preview is not None and self.preview.trial_id != self.trial_id:
            raise ValueError("Preview and trial IDs must match")

    @property
    def ok(self) -> bool:
        return self.preview is not None

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "ok": self.ok,
            "trial_id": str(self.trial_id),
            "requested_url": self.requested_url,
            "duration_seconds": round(self.duration_seconds, 6),
            "trace": self.trace.to_dict(),
            "image_trace": (
                self.preview.image_trace.to_dict()
                if self.preview is not None
                else FetchTrace().to_dict()
            ),
        }
        if self.preview is not None:
            result.update(
                final_url=self.preview.final_url,
                title=self.preview.title,
                description=self.preview.description,
                site_name=self.preview.site_name,
                image_data_url=self.preview.image_data_url,
            )
        else:
            assert self.failure is not None
            result.update(message=self.failure.message, failure=self.failure.to_dict())
        return result


def execute_preview(
    service: PreviewService, url: str, *, trial_id: UUID
) -> TrialExecution:
    """Measure only preview work; expected fetch failures remain trial outcomes."""
    started = monotonic()
    try:
        preview = service.create(url, trial_id=trial_id)
    except (FetchError, UnsupportedContentTypeError) as error:
        return TrialExecution(
            trial_id=trial_id,
            requested_url=url,
            duration_seconds=monotonic() - started,
            failure=TrialFailure(type(error).__name__, str(error)),
            trace=error.trace,
        )
    return TrialExecution(
        trial_id=trial_id,
        requested_url=url,
        duration_seconds=monotonic() - started,
        preview=preview,
        trace=preview.trace,
    )
