from typing import assert_never

from fastapi import FastAPI

from ssrf_link_preview_lab.api.routes.health import router as health_router
from ssrf_link_preview_lab.api.routes.preview import create_preview_router
from ssrf_link_preview_lab.fetching.disabled import DisabledFetcher
from ssrf_link_preview_lab.fetching.pycurl import PycurlFetcher
from ssrf_link_preview_lab.fetching.types import PageFetcher
from ssrf_link_preview_lab.preview.service import PreviewService
from ssrf_link_preview_lab.settings import AppSettings, FetchPolicy


def create_app(
    *,
    settings: AppSettings | None = None,
    fetcher: PageFetcher | None = None,
) -> FastAPI:
    resolved_settings = (
        settings if settings is not None else AppSettings.from_environment()
    )
    resolved_fetcher = (
        fetcher
        if fetcher is not None
        else _create_fetcher(resolved_settings.fetch_policy)
    )

    app = FastAPI(title="SSRF Link Preview Lab")
    app.include_router(health_router)
    app.include_router(create_preview_router(PreviewService(resolved_fetcher)))
    return app


def _create_fetcher(policy: FetchPolicy) -> PageFetcher:
    match policy:
        case FetchPolicy.DISABLED:
            return DisabledFetcher()
        case FetchPolicy.UNFILTERED:
            return PycurlFetcher()
    assert_never(policy)


app = create_app()
