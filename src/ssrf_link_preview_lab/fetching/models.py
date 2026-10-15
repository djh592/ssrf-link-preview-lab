from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FetchLimits:
    timeout_seconds: float = 10.0
    max_body_bytes: int = 1_000_000
    max_redirects: int = 5

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_body_bytes <= 0:
            raise ValueError("max_body_bytes must be positive")
        if self.max_redirects < 0:
            raise ValueError("max_redirects cannot be negative")


@dataclass(frozen=True, slots=True)
class FetchedPage:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str | None
    peer_ip: str | None
    body: bytes
