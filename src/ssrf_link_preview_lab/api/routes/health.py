from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


@router.get("/health")
async def get_health() -> HealthResponse:
    return HealthResponse()
