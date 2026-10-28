"""Operator-selected settings for one browser-demo trial."""

from dataclasses import dataclass
from enum import StrEnum


class Defense(StrEnum):
    NONE = "none"
    INITIAL = "initial"
    EACH_HOP = "each_hop"
    BOUND = "bound"


class DNSMode(StrEnum):
    STABLE = "stable"
    REBIND = "rebind"


@dataclass(frozen=True, slots=True)
class TrialConfiguration:
    defense: Defense = Defense.NONE
    dns_mode: DNSMode = DNSMode.STABLE

    def to_dict(self) -> dict[str, str]:
        return {
            "defense": self.defense.value,
            "dns_mode": self.dns_mode.value,
        }
