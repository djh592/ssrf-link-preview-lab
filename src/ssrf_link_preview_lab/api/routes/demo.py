"""HTTP routes for the isolated browser demonstration."""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from ssrf_link_preview_lab.demo.controller import DemoController
from ssrf_link_preview_lab.demo.models import Defense, DNSMode, TrialConfiguration


class TrialRequest(BaseModel):
    """The URL and experiment settings for one self-contained trial."""

    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, max_length=2_048)
    defense: Defense
    dns_mode: DNSMode


def create_demo_router(controller: DemoController) -> APIRouter:
    router = APIRouter(prefix="/demo", tags=["demo"])

    @router.get("/setup")
    def get_setup() -> dict[str, object]:
        return controller.setup()

    @router.post("/trial")
    def run_trial(request: TrialRequest) -> dict[str, object]:
        return controller.run(
            request.url,
            TrialConfiguration(defense=request.defense, dns_mode=request.dns_mode),
        )

    return router
