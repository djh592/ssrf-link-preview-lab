from fastapi import FastAPI

from ssrf_link_preview_lab.api.routes.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="SSRF Link Preview Lab")
    app.include_router(health_router)
    return app


app = create_app()
