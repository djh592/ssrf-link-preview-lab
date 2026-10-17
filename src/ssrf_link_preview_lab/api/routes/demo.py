"""HTTP routes for the isolated browser demonstration."""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from ssrf_link_preview_lab.demo.controller import DemoController
from ssrf_link_preview_lab.demo.models import Defense, DemoState, DNSMode


class StateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    defense: Defense
    dns_mode: DNSMode


class TrialRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2_048)


def create_demo_router(controller: DemoController) -> APIRouter:
    router = APIRouter(prefix="/demo", tags=["demo"])

    @router.get("/state")
    def get_state() -> dict[str, object]:
        return controller.state()

    @router.put("/state")
    def set_state(request: StateRequest) -> dict[str, object]:
        return controller.configure(
            DemoState(
                defense=request.defense,
                dns_mode=request.dns_mode,
            )
        )

    @router.post("/trial")
    def run_trial(request: TrialRequest) -> dict[str, object]:
        return controller.run(request.url)

    return router
