from html import escape
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse

from ssrf_link_preview_lab.lab.constants import INTERNAL_REPORT_MARKER
from ssrf_link_preview_lab.lab.events import (
    observation_headers,
    request_trial_id,
    write_event,
)

app = FastAPI(title="SSRF Lab Internal Report", docs_url=None, redoc_url=None)
_SUMMARY_IMAGE = Path(__file__).resolve().parent / "assets" / "access-review.png"


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
        f"Internal-only: 3 high-risk findings, 2 pending exceptions. Proof: {INTERNAL_REPORT_MARKER}",
        quote=True,
    )
    return HTMLResponse(
        f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Q3 Access Review | Operations Portal</title>
    <meta name="description" content="{description}">
    <meta property="og:title" content="Q3 Access Review">
    <meta property="og:description" content="{description}">
    <meta property="og:site_name" content="Operations Portal">
    <meta property="og:image" content="/summary.png">
    <style>
      * {{ box-sizing: border-box; }}
      body {{ margin: 0; color: #20352f; background: #f3f5f3; font: 16px/1.55 system-ui, sans-serif; }}
      header {{ padding: 24px max(24px, calc((100vw - 1000px) / 2)); color: #fff; background: #20352f; }}
      header div {{ max-width: 1000px; display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap; }}
      header strong {{ font-size: 18px; }}
      .classification {{ padding: 6px 10px; border-radius: 3px; background: #c3483f; font-size: 12px; font-weight: 700; }}
      main {{ max-width: 1000px; margin: 0 auto; padding: 48px 24px 70px; }}
      .eyebrow {{ color: #5c6c63; font-size: 12px; font-weight: 700; }}
      h1 {{ margin: 10px 0 8px; font-size: 54px; line-height: 1.1; }}
      .intro {{ max-width: 650px; color: #52655b; }}
      .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 36px 0; }}
      .metric {{ padding: 20px; border: 1px solid #d8dfdb; background: #fff; }}
      .metric strong {{ display: block; font-size: 38px; line-height: 1.1; }}
      .metric:first-child strong {{ color: #b63f39; }}
      .metric span {{ color: #53675b; font-size: 13px; font-weight: 700; }}
      h2 {{ margin-top: 42px; font-size: 20px; }}
      .finding {{ display: grid; grid-template-columns: minmax(130px, 1fr) minmax(0, 2fr); gap: 16px; padding: 18px 0; border-top: 1px solid #d8dfdb; }}
      .finding p {{ margin: 0; color: #52655b; }}
      footer {{ margin-top: 42px; padding-top: 18px; border-top: 1px solid #d8dfdb; color: #667a6e; font-size: 12px; overflow-wrap: anywhere; }}
      @media (max-width: 540px) {{ h1 {{ font-size: 32px; }} .finding {{ grid-template-columns: 1fr; gap: 4px; }} }}
    </style>
  </head>
  <body data-trial-id="{rendered_trial_id}">
    <header><div><strong>Operations Portal</strong><span class="classification">INTERNAL / RESTRICTED</span></div></header>
    <main>
      <p class="eyebrow">SECURITY OPERATIONS / Q3 2026</p>
      <h1>Access Review</h1>
      <p class="intro">Privileged access, outstanding exceptions, and remediation ownership across production systems.</p>
      <section class="metrics" aria-label="Review summary">
        <div class="metric"><strong>03</strong><span>High-risk findings</span></div>
        <div class="metric"><strong>02</strong><span>Pending exceptions</span></div>
        <div class="metric"><strong>01</strong><span>Overdue sign-off</span></div>
      </section>
      <h2>Items requiring action</h2>
      <div class="finding"><strong>Production administrator role</strong><p>A shared service account still permits interactive sign-in. Owner: Platform Engineering.</p></div>
      <div class="finding"><strong>Backup console access</strong><p>The quarterly review is overdue. Owner: Infrastructure.</p></div>
      <div class="finding"><strong>Vendor SSO exception</strong><p>Time-limited access is pending security approval. Owner: Identity Team.</p></div>
      <footer>Document OPS-AR-2026-Q3 · Proof token: {INTERNAL_REPORT_MARKER}<br>Trial: {rendered_trial_id}<br>All report values are synthetic and exist only inside this controlled lab.</footer>
    </main>
  </body>
</html>
""",
        headers=observation_headers(request, "internal-report"),
    )


@app.get("/summary.png", include_in_schema=False)
def summary_image(request: Request) -> FileResponse:
    return FileResponse(
        _SUMMARY_IMAGE,
        media_type="image/png",
        headers=observation_headers(request, "internal-report"),
    )
