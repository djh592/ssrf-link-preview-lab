from dataclasses import dataclass
from uuid import UUID

from ssrf_link_preview_lab.fetching.models import FetchTrace


@dataclass(frozen=True, slots=True)
class PageMetadata:
    title: str | None
    description: str | None


@dataclass(frozen=True, slots=True)
class Preview:
    trial_id: UUID
    requested_url: str
    final_url: str
    title: str | None
    description: str | None
    trace: FetchTrace
