from os import environ
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ssrf_link_preview_lab.lab.events import request_trial_id, write_event

_DEFAULT_INTERNAL_REPORT_URL = "http://internal-report:8080/report"

app = FastAPI(title="SSRF Lab External Service", docs_url=None, redoc_url=None)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/page", response_class=HTMLResponse)
@app.get("/report", response_class=HTMLResponse)
def page(request: Request) -> HTMLResponse:
    trial_id = request_trial_id(request)
    write_event("external_page_access", request, trial_id=trial_id)
    return HTMLResponse(
        """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Controlled external page</title>
    <meta name="description" content="A benign page in the isolated lab">
  </head>
</html>
"""
    )


@app.get("/redirect/internal")
def redirect_to_internal(request: Request) -> RedirectResponse:
    trial_id = request_trial_id(request)
    target = _internal_report_url(trial_id)
    write_event(
        "external_redirect",
        request,
        trial_id=trial_id,
        location=target,
    )
    return RedirectResponse(target, status_code=302)


@app.get("/redirect/page")
def redirect_to_page(request: Request) -> RedirectResponse:
    trial_id = request_trial_id(request)
    target = "http://external-page:8080/page"
    write_event("external_redirect", request, trial_id=trial_id, location=target)
    return RedirectResponse(target, status_code=302)


def _internal_report_url(trial_id: str | None) -> str:
    base_url = environ.get("SSRF_LAB_INTERNAL_REPORT_URL", _DEFAULT_INTERNAL_REPORT_URL)
    if trial_id is None:
        return base_url

    parsed = urlsplit(base_url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    query.append(("source_trial_id", trial_id))
    return urlunsplit(parsed._replace(query=urlencode(query)))
