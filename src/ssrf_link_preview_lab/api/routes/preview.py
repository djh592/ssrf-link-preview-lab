from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ssrf_link_preview_lab.fetching.errors import (
    FetchError,
    FetchingDisabledError,
    InvalidUrlError,
)
from ssrf_link_preview_lab.preview.errors import UnsupportedContentTypeError
from ssrf_link_preview_lab.preview.service import PreviewService


class PreviewRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2_048)


class PreviewResponse(BaseModel):
    requested_url: str
    final_url: str
    title: str | None
    description: str | None


def create_preview_router(service: PreviewService) -> APIRouter:
    router = APIRouter(tags=["preview"])

    @router.post("/preview")
    def create_preview(request: PreviewRequest) -> PreviewResponse:
        try:
            preview = service.create(request.url)
        except FetchingDisabledError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "fetching_disabled", "message": str(error)},
            ) from error
        except InvalidUrlError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"code": "invalid_url", "message": str(error)},
            ) from error
        except (FetchError, UnsupportedContentTypeError) as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"code": "preview_failed", "message": str(error)},
            ) from error

        return PreviewResponse(
            requested_url=preview.requested_url,
            final_url=preview.final_url,
            title=preview.title,
            description=preview.description,
        )

    return router
