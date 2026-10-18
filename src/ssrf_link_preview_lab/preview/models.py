from dataclasses import dataclass, field
from uuid import UUID

from ssrf_link_preview_lab.fetching.models import FetchTrace


@dataclass(frozen=True, slots=True)
class PageMetadata:
    title: str | None
    description: str | None
    site_name: str | None = None
    image_url: str | None = None


@dataclass(frozen=True, slots=True)
class Preview:
    trial_id: UUID
    requested_url: str
    final_url: str
    title: str | None
    description: str | None
    trace: FetchTrace
    site_name: str | None = None
    image_data_url: str | None = None
    image_trace: FetchTrace = field(default_factory=FetchTrace)
