from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import assert_never

from fastapi import FastAPI

from ssrf_link_preview_lab.api.routes.demo import create_demo_router
from ssrf_link_preview_lab.api.routes.health import router as health_router
from ssrf_link_preview_lab.api.routes.preview import create_preview_router
from ssrf_link_preview_lab.demo.controller import DemoController
from ssrf_link_preview_lab.fetching.disabled import DisabledFetcher
from ssrf_link_preview_lab.fetching.protocols import PageFetcher
from ssrf_link_preview_lab.fetching.redirecting import RedirectingFetcher
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

    controller = DemoController() if resolved_settings.demo_enabled else None

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        try:
            yield
        finally:
            if controller is not None:
                controller.close()

    app = FastAPI(title="SSRF Link Preview Lab", lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(create_preview_router(PreviewService(resolved_fetcher)))
    if controller is not None:
        app.include_router(create_demo_router(controller))

    return app


def _create_fetcher(policy: FetchPolicy) -> PageFetcher:
    match policy:
        case FetchPolicy.DISABLED:
            return DisabledFetcher()
        case FetchPolicy.UNFILTERED:
            return RedirectingFetcher()
    assert_never(policy)


app = create_app()
