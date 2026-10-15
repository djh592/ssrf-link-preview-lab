from dataclasses import dataclass
from enum import StrEnum
from os import environ


class FetchPolicy(StrEnum):
    DISABLED = "disabled"
    UNFILTERED = "unfiltered"


@dataclass(frozen=True, slots=True)
class AppSettings:
    fetch_policy: FetchPolicy = FetchPolicy.DISABLED

    @classmethod
    def from_environment(cls) -> "AppSettings":
        raw_policy = environ.get("SSRF_LAB_FETCH_POLICY", FetchPolicy.DISABLED)
        try:
            policy = FetchPolicy(raw_policy)
        except ValueError as error:
            choices = ", ".join(policy.value for policy in FetchPolicy)
            raise ValueError(
                f"Invalid SSRF_LAB_FETCH_POLICY={raw_policy!r}; expected one of: {choices}."
            ) from error
        return cls(fetch_policy=policy)
