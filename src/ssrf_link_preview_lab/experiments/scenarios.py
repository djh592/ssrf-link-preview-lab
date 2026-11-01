"""Named offline cases whose targets remain inside the isolated testbed."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

type ScenarioKind = Literal["normal", "attack"]


class Scenario(StrEnum):
    NORMAL_PAGE = "normal_page"
    NORMAL_REDIRECT = "normal_redirect"
    NORMAL_REDIRECT_THREE = "normal_redirect_three"
    DIRECT_INTERNAL_IP = "direct_internal_ip"
    INTERNAL_SERVICE_NAME = "internal_service_name"
    REDIRECT_INTERNAL = "redirect_internal"
    REDIRECT_INTERNAL_THREE = "redirect_internal_three"


@dataclass(frozen=True, slots=True)
class ScenarioCase:
    name: Scenario
    kind: ScenarioKind
    target_url: str
    expected_title: str | None = None
    expected_description: str | None = None


_EXTERNAL_DESCRIPTION = "A short field note from the controlled external site."


def case_for(scenario: Scenario, *, internal_ip: str) -> ScenarioCase:
    """Resolve only the direct-IP case at runtime; never accept arbitrary batch URLs."""
    match scenario:
        case Scenario.NORMAL_PAGE:
            return ScenarioCase(
                scenario,
                "normal",
                "http://external-page:8080/page",
                "Field Notes: An external page",
                _EXTERNAL_DESCRIPTION,
            )
        case Scenario.NORMAL_REDIRECT:
            return ScenarioCase(
                scenario,
                "normal",
                "http://external-page:8080/redirect/page",
                "Field Notes: An external page",
                _EXTERNAL_DESCRIPTION,
            )
        case Scenario.NORMAL_REDIRECT_THREE:
            return ScenarioCase(
                scenario,
                "normal",
                "http://external-page:8080/redirect/chain/3/page",
                "Field Notes: An external page",
                _EXTERNAL_DESCRIPTION,
            )
        case Scenario.DIRECT_INTERNAL_IP:
            return ScenarioCase(scenario, "attack", f"http://{internal_ip}:8080/report")
        case Scenario.INTERNAL_SERVICE_NAME:
            return ScenarioCase(
                scenario, "attack", "http://internal-report:8080/report"
            )
        case Scenario.REDIRECT_INTERNAL:
            return ScenarioCase(
                scenario, "attack", "http://external-page:8080/redirect/internal"
            )
        case Scenario.REDIRECT_INTERNAL_THREE:
            return ScenarioCase(
                scenario,
                "attack",
                "http://external-page:8080/redirect/chain/3/internal",
            )
