# SSRF Link Preview Lab

SSRF Link Preview Lab is an isolated environment for exploring how a link preview service handles attacker-controlled URLs. It demonstrates direct access to an internal service, redirects through an external service, DNS rebinding, and defenses at different stages of a request. The browser interface shows the generated preview alongside the HTTP hops, DNS answers, and address decisions behind it.

## Safety and network layout

The lab contains three Docker services: `preview`, `external-page`, and `internal-report`. The preview service connects to both Docker networks; the external page and internal report each connect to only one. Both networks are marked `internal: true`; no container ports are published, and no host directories, devices, or Docker socket are mounted into the containers. The internal report contains a synthetic marker, not real private data.

The standalone `/preview` API has network fetching disabled by default. The isolated command-line baseline deliberately enables an unfiltered fetcher inside Compose. Do not expose that policy to untrusted users or run it outside an authorized, isolated environment. On a shared machine, choose a unique `SSRF_LAB_INSTANCE` so the lab only manages its own containers and networks.

## Browser demo

Requirements: Docker with Compose, `uv`, and Python 3.13 or newer. From the repository root:

```bash
uv sync --locked
export SSRF_LAB_INSTANCE="yourname-browser"
uv run --no-sync python scripts/run_browser_demo.py
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). The launcher builds one image, starts the three isolated services, and serves the presentation page on the host's loopback interface. It refuses to take over an instance that already has containers. Set `SSRF_LAB_PORT` before launching if port 8765 is unavailable.

A useful sequence is:

1. Preview the external page, then the internal URL, with no address check.
2. Enable **Initial URL only**. The direct internal request is blocked, but a redirect from the external page to the internal report still succeeds.
3. Enable **Every redirect hop**. The redirected internal destination is blocked.
4. Select **Rebinding** and preview `rebind.lab`. The address check sees the external address, while the later connection uses the internal address.
5. Enable **Check and bind**. The HTTP client connects to the address that passed the check, so the rebinding attempt no longer reaches the internal report.

The redirect controls choose example URLs; they do not start or stop containers. Each trial displays its result and request evidence, and the download button saves the trial record as JSON. The demo API accepts only the three lab hostnames (`external-page`, `internal-report`, and `rebind.lab`) on port 8080. The ordinary `/preview` endpoint remains disabled in this mode.

The presentation server forwards only the demo API operations to the running preview container through project-scoped `docker compose exec`. It does not fetch the submitted URL itself. This bridge adds overhead, so browser round-trip time is not a measure of preview fetch latency.

Press Ctrl+C in the launcher terminal to stop the demo and remove its containers and networks. If cleanup was interrupted, run this from the repository root with the same instance name:

```bash
docker compose -f compose.yaml -f compose.demo.yaml --project-name "ssrf-link-preview-${SSRF_LAB_INSTANCE}" down --remove-orphans
```

## Automated redirect baseline

The baseline runs the unfiltered preview service inside the same three-service topology. It checks that the external container cannot reach the internal report directly, then verifies that the preview service follows an external redirect to the internal report and returns the synthetic marker.

After installing the dependencies as shown above, use a separate instance name from the browser demo. Build the image once, then run the baseline with readable terminal output or select JSON output for automation:

```bash
export SSRF_LAB_INSTANCE="yourname-redirect"
COMPOSE_PARALLEL_LIMIT=1 docker compose --project-name "ssrf-link-preview-${SSRF_LAB_INSTANCE}" build preview
uv run --no-sync python scripts/run_redirect_baseline.py
# For JSON output: uv run --no-sync python scripts/run_redirect_baseline.py --format json
```

Each run starts and stops only its own Compose project and saves a raw trial record under `results/`. Text output shows the request path and evidence checks; `--format json` prints the same result for automation. The command exits nonzero when verification fails. Do not run two copies concurrently with the same instance name.

If a baseline run is interrupted before cleanup, remove only its project:

```bash
docker compose --project-name "ssrf-link-preview-${SSRF_LAB_INSTANCE}" down --remove-orphans
```

Avoid daemon-wide cleanup commands such as `docker system prune` on a shared host. The runtime limits are 0.5 CPU, 256 MB, and 96 PIDs for `preview`, plus 0.25 CPU, 128 MB, and 64 PIDs for each lab service. Image builds are not covered by those runtime limits; the browser launcher and build command above limit Compose parallelism to one.

## Implementation and scope

`PreviewService` extracts HTML metadata after a `PageFetcher` retrieves a page. `RedirectingFetcher` handles the redirect loop and applies an optional address policy; `PycurlTransport` performs one HTTP request per hop. The browser demo keeps defense and DNS state in `demo/models.py`, lab address checks in `demo/policy.py`, and trial orchestration in `demo/controller.py`; redirect examples only fill the URL field in the browser. Trial IDs connect API responses, fetch traces, and lab service events.

The browser defense uses the external lab service's IP as an allowlisted stand-in for a public address. Docker gives both lab zones private IPs, so this is not a production public-IP classifier. The DNS example uses a loopback-only, zero-TTL authority. Because this libcurl build cannot use a custom DNS server directly, the demo performs the connection-stage query itself and passes the answer to PycURL with `CURLOPT_RESOLVE`. The trace records the actual HTTP peer; it does not claim that libcurl made the second DNS query.

The repository currently includes one automated redirect baseline and an interactive defense demonstration. It does not yet include a safehttpx comparison, repeated timing and success-rate measurements, a no-redirect policy, or broader DNS cache and TTL experiments.

## Development

To run the API locally with fetching disabled:

```bash
uv run --no-sync fastapi dev src/ssrf_link_preview_lab/api/app.py
```

API documentation is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Do not enable the unfiltered policy on a shared host; use the isolated Compose baseline instead.

Run the project checks with:

```bash
uv run --no-sync ruff format --check .
uv run --no-sync ruff check .
uv run --no-sync ty check
uv run --no-sync pytest
```
