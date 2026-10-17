from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ssrf_link_preview_lab.fetching.errors import (
    FetchError,
    FetchingDisabledError,
    InvalidUrlError,
)
from ssrf_link_preview_lab.preview.errors import UnsupportedContentTypeError
from ssrf_link_preview_lab.preview.service import PreviewService
from ssrf_link_preview_lab.tracing import write_structured_event


class PreviewRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2_048)


class PreviewResponse(BaseModel):
    trial_id: UUID
    requested_url: str
    final_url: str
    title: str | None
    description: str | None


def create_preview_router(service: PreviewService) -> APIRouter:
    router = APIRouter(tags=["preview"])

    @router.post("/preview")
    def create_preview(request: PreviewRequest) -> PreviewResponse:
        trial_id = uuid4()
        try:
            preview = service.create(request.url, trial_id=trial_id)
        except FetchingDisabledError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "trial_id": str(trial_id),
                    "code": "fetching_disabled",
                    "message": str(error),
                },
            ) from error
        except InvalidUrlError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "trial_id": str(trial_id),
                    "code": "invalid_url",
                    "message": str(error),
                },
            ) from error
        except (FetchError, UnsupportedContentTypeError) as error:
            if isinstance(error, FetchError):
                write_structured_event(
                    "preview_fetch_failed",
                    trial_id=trial_id,
                    error=type(error).__name__,
                    message=str(error),
                    trace=error.trace.to_dict(),
                )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "trial_id": str(trial_id),
                    "code": "preview_failed",
                    "message": str(error),
                },
            ) from error

        write_structured_event(
            "preview_fetch_completed",
            trial_id=trial_id,
            requested_url=preview.requested_url,
            final_url=preview.final_url,
            trace=preview.trace.to_dict(),
        )
        return PreviewResponse(
            trial_id=preview.trial_id,
            requested_url=preview.requested_url,
            final_url=preview.final_url,
            title=preview.title,
            description=preview.description,
        )

    return router
