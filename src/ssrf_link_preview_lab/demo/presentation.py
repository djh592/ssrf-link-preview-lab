"""Serve the UI locally without publishing a lab-container port."""

import json
from asyncio import to_thread
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ssrf_link_preview_lab.experiments.compose import ComposeProject

_ASSETS = Path(__file__).resolve().parent / "static"
_MAX_REQUEST_BYTES = 4_096
_ROUTES = {
    ("GET", "state"),
    ("PUT", "state"),
    ("POST", "trial"),
}


def create_presentation_app(project: ComposeProject) -> FastAPI:
    """Expose static assets and forward only the three demo API operations.

    The host process never fetches submitted URLs. It invokes the preview API
    inside the named Compose project and limits forwarded request bodies.
    """
    app = FastAPI(title="SSRF Lab Presentation", docs_url=None, redoc_url=None)
    app.mount("/assets", StaticFiles(directory=_ASSETS), name="demo-assets")

    @app.get("/", include_in_schema=False)
    def page() -> FileResponse:
        return FileResponse(_ASSETS / "index.html")

    @app.get("/health", include_in_schema=False)
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.api_route("/demo/{path}", methods=["GET", "PUT", "POST"])
    async def demo(request: Request, path: str) -> Response:
        if (request.method, path) not in _ROUTES:
            raise HTTPException(status_code=404, detail="Not a demo operation")
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > _MAX_REQUEST_BYTES:
                raise HTTPException(status_code=413, detail="Request body is too large")
        try:
            result = await to_thread(
                project.exec_module,
                "preview",
                "ssrf_link_preview_lab.demo.container_client",
                request.method,
                f"/demo/{path}",
                body.decode("utf-8"),
            )
            envelope = json.loads(result.stdout)
            status_code = envelope["status_code"]
            payload = envelope["body"]
            if not isinstance(status_code, int):
                raise TypeError("Invalid demo API status")
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as error:
            raise HTTPException(
                status_code=502, detail="Demo service is unavailable"
            ) from error
        return Response(
            content=json.dumps(payload, ensure_ascii=False),
            status_code=status_code,
            media_type="application/json",
        )

    return app
