from os import environ
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from ssrf_link_preview_lab.lab.events import (
    observation_headers,
    request_trial_id,
    write_event,
)

_DEFAULT_INTERNAL_REPORT_URL = "http://internal-report:8080/report"
_COVER = Path(__file__).resolve().parent / "assets" / "field-notes.png"

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
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Field Notes | An external page</title>
    <meta name="description" content="A short field note from the controlled external site.">
    <meta property="og:title" content="Field Notes: An external page">
    <meta property="og:description" content="A short field note from the controlled external site.">
    <meta property="og:site_name" content="Field Notes">
    <meta property="og:image" content="http://external-page:8080/cover.png">
    <style>
      body { margin: 0; font: 17px/1.65 system-ui, sans-serif; color: #1d312c; background: #f4f7f5; }
      article { max-width: 720px; margin: 64px auto; padding: 0 24px; }
      img { display: block; width: 100%; aspect-ratio: 16 / 9; object-fit: cover; }
      small { color: #28765d; font-weight: 700; text-transform: uppercase; }
      h1 { font-size: 38px; line-height: 1.15; margin: 18px 0; }
    </style>
  </head>
  <body>
    <article>
      <small>Field Notes / External site</small>
      <h1>An external page</h1>
      <p>This ordinary article lives in the lab's external network. A link preview reads its metadata without rendering the page.</p>
      <img src="/cover.png" alt="A desk with an open field notebook">
    </article>
  </body>
</html>
""",
        headers=observation_headers(request, "external-page"),
    )


@app.get("/cover.png", include_in_schema=False)
def cover(request: Request) -> FileResponse:
    return FileResponse(
        _COVER,
        media_type="image/png",
        headers=observation_headers(request, "external-page"),
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
    return RedirectResponse(
        target,
        status_code=302,
        headers=observation_headers(request, "external-page"),
    )


@app.get("/redirect/page")
def redirect_to_page(request: Request) -> RedirectResponse:
    trial_id = request_trial_id(request)
    target = "http://external-page:8080/page"
    write_event("external_redirect", request, trial_id=trial_id, location=target)
    return RedirectResponse(
        target,
        status_code=302,
        headers=observation_headers(request, "external-page"),
    )


@app.get("/redirect/chain/{remaining}/{destination}")
def redirect_chain(
    request: Request, remaining: int, destination: str
) -> RedirectResponse:
    """Return exactly the requested number of redirects, up to three."""
    if remaining not in {1, 2, 3} or destination not in {"page", "internal"}:
        raise HTTPException(status_code=404, detail="Unknown redirect chain")
    trial_id = request_trial_id(request)
    if remaining > 1:
        target = (
            f"http://external-page:8080/redirect/chain/{remaining - 1}/{destination}"
        )
    elif destination == "internal":
        target = _internal_report_url(trial_id)
    else:
        target = "http://external-page:8080/page"
    write_event("external_redirect", request, trial_id=trial_id, location=target)
    return RedirectResponse(
        target,
        status_code=302,
        headers=observation_headers(request, "external-page"),
    )


def _internal_report_url(trial_id: str | None) -> str:
    base_url = environ.get("SSRF_LAB_INTERNAL_REPORT_URL", _DEFAULT_INTERNAL_REPORT_URL)
    if trial_id is None:
        return base_url

    parsed = urlsplit(base_url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    query.append(("source_trial_id", trial_id))
    return urlunsplit(parsed._replace(query=urlencode(query)))
