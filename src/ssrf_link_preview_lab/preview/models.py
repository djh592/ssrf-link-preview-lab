from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PageMetadata:
    title: str | None
    description: str | None


@dataclass(frozen=True, slots=True)
class Preview:
    requested_url: str
    final_url: str
    title: str | None
    description: str | None
