"""Specifications, evidence checks, and saved results for automated trials."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from ssrf_link_preview_lab.experiments.event_models import TrialEvent


class ExecutionStatus(StrEnum):
    COMPLETED = "completed"
    ERROR = "error"


class VerificationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class SecurityOutcome(StrEnum):
    VULNERABLE = "vulnerable"
    PROTECTED = "protected"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True, slots=True)
class TrialSpec:
    scenario: str
    policy: str
    target_url: str
    expected_security_outcome: SecurityOutcome

    def to_dict(self) -> dict[str, object]:
        return {
            "scenario": self.scenario,
            "policy": self.policy,
            "target_url": self.target_url,
            "expected_security_outcome": self.expected_security_outcome,
        }


@dataclass(frozen=True, slots=True)
class EvidenceCheck:
    key: str
    label: str
    satisfied: bool
    satisfied_label: str
    unsatisfied_label: str

    @property
    def observed_label(self) -> str:
        return self.satisfied_label if self.satisfied else self.unsatisfied_label

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "label": self.label,
            "satisfied": self.satisfied,
            "observed": self.observed_label,
        }


@dataclass(frozen=True, slots=True)
class PreviewObservation:
    trial_id: UUID
    requested_url: str
    final_url: str
    title: str | None
    description: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "trial_id": str(self.trial_id),
            "requested_url": self.requested_url,
            "final_url": self.final_url,
            "title": self.title,
            "description": self.description,
        }


@dataclass(frozen=True, slots=True)
class TrialResult:
    spec: TrialSpec
    trial_id: UUID
    verification_status: VerificationStatus
    observed_security_outcome: SecurityOutcome
    evidence: tuple[EvidenceCheck, ...]
    preview: PreviewObservation
    events: tuple[TrialEvent, ...]

    def __post_init__(self) -> None:
        if self.preview.trial_id != self.trial_id:
            raise ValueError("The preview and trial result IDs must match")
        evidence_keys = [check.key for check in self.evidence]
        if len(evidence_keys) != len(set(evidence_keys)):
            raise ValueError("Evidence check keys must be unique")

    def to_dict(self) -> dict[str, object]:
        return {
            "trial_id": str(self.trial_id),
            "verification_status": self.verification_status,
            "observed_security_outcome": self.observed_security_outcome,
            "evidence": [check.to_dict() for check in self.evidence],
            "preview": self.preview.to_dict(),
            "events": [event.to_dict() for event in self.events],
        }


@dataclass(frozen=True, slots=True)
class TrialError:
    error_type: str
    message: str

    @classmethod
    def from_exception(cls, error: Exception) -> "TrialError":
        return cls(error_type=type(error).__name__, message=str(error))

    def to_dict(self) -> dict[str, str]:
        return {"type": self.error_type, "message": self.message}


@dataclass(frozen=True, slots=True)
class TrialRun:
    spec: TrialSpec
    status: ExecutionStatus
    started_at: datetime
    duration_seconds: float
    result: TrialResult | None = None
    error: TrialError | None = None

    def __post_init__(self) -> None:
        if self.started_at.tzinfo is None:
            raise ValueError("started_at must include a timezone")
        if self.duration_seconds < 0:
            raise ValueError("duration_seconds cannot be negative")
        if self.status is ExecutionStatus.COMPLETED:
            if self.result is None or self.error is not None:
                raise ValueError("A completed run requires a result and no error")
            if self.result.spec != self.spec:
                raise ValueError(
                    "The trial result does not match the run specification"
                )
        elif self.result is not None or self.error is None:
            raise ValueError("An errored run requires an error and no result")

    @property
    def verification_passed(self) -> bool:
        return (
            self.result is not None
            and self.result.verification_status is VerificationStatus.PASSED
        )

    def to_dict(self) -> dict[str, object]:
        record: dict[str, object] = {
            **self.spec.to_dict(),
            "execution": {
                "status": self.status,
                "started_at": self.started_at.isoformat(timespec="milliseconds"),
                "duration_seconds": round(self.duration_seconds, 6),
            },
        }
        if self.result is not None:
            record["result"] = self.result.to_dict()
        if self.error is not None:
            record["error"] = self.error.to_dict()
        return record
