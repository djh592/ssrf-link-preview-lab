from html import escape

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from ssrf_link_preview_lab.lab.constants import INTERNAL_REPORT_MARKER
from ssrf_link_preview_lab.lab.events import request_trial_id, write_event

app = FastAPI(title="SSRF Lab Internal Report", docs_url=None, redoc_url=None)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/report", response_class=HTMLResponse)
def report(request: Request, source_trial_id: str | None = None) -> HTMLResponse:
    trial_id = request_trial_id(request)
    write_event(
        "internal_report_access",
        request,
        trial_id=trial_id,
        source_trial_id=source_trial_id,
        trial_ids_match=trial_id is not None and trial_id == source_trial_id,
    )

    rendered_trial_id = escape(trial_id or "missing", quote=True)
    description = escape(
        f"{INTERNAL_REPORT_MARKER}; trial_id={trial_id or 'missing'}",
        quote=True,
    )
    return HTMLResponse(
        f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Internal report</title>
    <meta name="description" content="{description}">
  </head>
  <body data-trial-id="{rendered_trial_id}">
    Synthetic internal report for the controlled SSRF lab.
  </body>
</html>
"""
    )
