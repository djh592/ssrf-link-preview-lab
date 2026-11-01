# SSRF Link Preview Lab

SSRF Link Preview Lab is a link preview service and a controlled environment for studying server-side request forgery. It generates previews from live public websites and from two lab websites, then shows the HTTP hops, DNS answers, and address decisions behind each result. The lab websites support direct internal access, redirects, DNS rebinding, and defenses at different stages of a request.

## Safety and network layout

The lab contains three Docker services: `preview`, `external-page`, and `internal-report`. The preview service connects to both isolated Docker networks; the external page and internal report each connect to only one. The internal report contains a synthetic marker, not real private data. The command-line baseline has no Internet route and publishes no container ports.

The browser demo additionally connects only `preview` to a public egress network and publishes its UI on the host's `127.0.0.1` interface. It checks and binds each connection to a globally routable IPv4 address or one of the two synthetic lab service addresses. Public web requests are limited to ports 80 and 443; lab requests use port 8080. This application check is not an independent network firewall. Run the public-egress demo only on a personal, authorized machine, not on a shared host or as a publicly exposed service. No host directories, devices, or Docker socket are mounted into the containers.

The ordinary `/preview` API has network fetching disabled by default. The isolated command-line baseline deliberately enables an unfiltered fetcher inside Compose. Do not expose that policy to untrusted users. Choose a unique `SSRF_LAB_INSTANCE` so each run manages only its own resources.

## Browser demo

Requirements: Docker with Compose, `uv`, and Python 3.13 or newer. From the repository root:

```bash
uv sync --locked
export SSRF_LAB_INSTANCE="yourname-browser"
export SSRF_LAB_PUBLIC_EGRESS=1
uv run --no-sync python scripts/run_browser_demo.py
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). The launcher builds one image and starts the three services; the preview container serves both the UI and API. It refuses to take over an instance that already has containers. Set `SSRF_LAB_PORT` before launching if port 8765 is unavailable. The explicit egress setting is required because the demo can contact live websites.

A useful sequence is:

1. Select **Browser** and generate previews for the attacker web page and a public website. Select **Private report**, use its URL, and submit it from Browser with no lab check.
2. Select **Preview** and enable **Initial URL**. The direct internal request is blocked. Select **Attacker web**, choose **302 → private report**, then submit the selected URL from Browser; the redirect still reaches the report.
3. Set Preview to **Each hop** and retry the redirect. The redirected internal destination is blocked.
4. Select **DNS**, enable **Rebinding**, then use its `rebind.lab` URL and submit it from Browser. The address check sees the external address, while the later connection uses the internal address.
5. Set Preview to **Check & bind** and retry the DNS name. The HTTP client connects to the address that passed the check, so the rebinding attempt no longer reaches the internal report.
6. Select **No redirects** on Preview and retry the attacker's 302 to the private report. The first response is recorded, but no second HTTP request is sent. Direct normal pages still work under this policy.

The network workspace combines the testbed map with node-specific controls. Selecting a device opens its controls beside the map on wide screens or in a dismissible bottom panel on narrow screens; selecting a device does not scroll the page. Browser submits a URL; Preview selects the outgoing address policy; the DNS component selects the answer sequence of a loopback authority inside Preview. Each destination node can fill Browser with its URL. The attacker-web choices select real external-service endpoints that return a page or an HTTP 302; they do not mutate the external server globally.

Settings are submitted with each trial, so changing them does not rewrite the evidence of an earlier trial. Once a trial is recorded, the map's node labels and paths both describe that trial until another is submitted. A failed API request also leaves the previous trial visible. The map places the host browser, three Docker services, two isolated lab networks, the browser demo's `public_egress` network, and public Internet in fixed locations. Muted lines show network links; selecting an HTTP event highlights the observed peer, while earlier responses remain faint. A redirect produces another request from Preview, not a connection between the two destination servers. A blocked request stops inside Preview, and an unconfirmed connection attempt stops near Preview rather than claiming delivery. DNS answers can also be selected to inspect the local authority's reply. The map uses application-level observations, not predicted routes or packet capture. The download button saves the raw traces and projected observations as JSON.

The same preview pipeline fetches both real public pages and lab pages. It accepts canonical ASCII hostnames or IPv4 literals, and extracts HTML metadata without running page scripts. Open Graph images are fetched separately through the same address policy, limited to one megabyte, and embedded in the returned card; browsers never request the remote image URL directly. Websites without suitable metadata or with restrictive bot policies may produce a text-only preview or a fetch error. The ordinary `/preview` endpoint remains disabled in the browser demo.

The address-defense controls describe the lab experiment. Even "No lab address check" retains the connection boundary that blocks access to real private networks. The DNS rebinding example uses a trial-scoped UDP authority; this libcurl build cannot select that server directly, so the connection-stage query is performed by the demo and its answer is supplied to PycURL with `CURLOPT_RESOLVE`. The trace does not claim that libcurl made the second query.

The browser response includes the elapsed preview time. A generated preview can make a separate image request; the reported time includes that work. Offline measurements disable image fetching so the main-page outcome and latency have one consistent meaning.

Press Ctrl+C in the launcher terminal to stop the demo and remove its containers and networks. If cleanup was interrupted, run this from the repository root with the same instance name:

```bash
docker compose -f compose.yaml -f compose.demo.yaml -f compose.public.yaml --project-name "ssrf-link-preview-${SSRF_LAB_INSTANCE}" down --remove-orphans
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

## Offline policy measurements

The measurement runner uses the isolated three-service topology without public egress. It starts one Compose instance, runs each trial sequentially, and stops only that instance. It covers a normal page, normal 1- and 3-redirect pages, direct internal IP, a stable internal service name, and 1- and 3-redirect attacks. Policies are no check, initial check, each-hop check, check and bind, and no redirects. Each repetition shuffles the scenario-policy combinations using a saved seed.

Build the shared image once, then start with a single trial on a personal Docker host:

```bash
export SSRF_LAB_INSTANCE="yourname-measure"
COMPOSE_PARALLEL_LIMIT=1 docker compose -f compose.yaml -f compose.measure.yaml --project-name "ssrf-link-preview-${SSRF_LAB_INSTANCE}" build preview
uv run --no-sync python scripts/run_measurements.py --scenario redirect_internal --defense each_hop --repetitions 1
```

The runner accepts repeated `--scenario` and `--defense` arguments. For example, all three normal scenarios at 50 repetitions across five policies require `--repetitions 50 --max-trials 750`; the default cap is 100 trials and the hard cap is 1,000 per invocation. Split larger plans into separately named runs. Each attempted trial is flushed to `results/<run-id>/trials.jsonl`; `summary.json` reports access, disclosure, normal success, median/P95 successful-preview latency, and failure reasons. The elapsed measurement begins inside the preview worker, so Compose startup and CLI overhead are excluded. Rates are omitted when a trial's service evidence is unavailable. A Ctrl+C stops further trials, keeps completed trial records, and triggers instance-scoped cleanup. Reuse the baseline cleanup command above if teardown is interrupted.

The internal-access metric comes from `internal-report` service logs. Disclosure requires both the marker in returned metadata and the internal service's matching response identity in the final HTTP hop. A connection attempt or an expected blocked fetch is never treated as an infrastructure error.

## Recursive DNS probe

The separate DNS overlay adds a controlled authoritative server and an Unbound caching resolver. Preview uses the resolver through its container DNS configuration; the validator and libcurl are not given synthetic connection-stage answers. This path is a prototype until its queries, cache behavior, and peer addresses have been checked on the machine used for the experiment. It remains offline; building the Unbound image requires a one-time package download.

On a personal Docker host, build both images and run one TTL-zero rebinding probe:

```bash
export SSRF_LAB_INSTANCE="yourname-dns"
COMPOSE_PARALLEL_LIMIT=1 docker compose -f compose.yaml -f compose.measure.yaml -f compose.dns.yaml --project-name "ssrf-link-preview-${SSRF_LAB_INSTANCE}" build preview resolver
uv run --no-sync python scripts/probe_recursive_dns.py --mode rebind --ttl 0 --cache empty --defense each_hop
```

The probe saves the fetch trace, authority answers, resolver log lines, and internal-service events in `results/dns-probe-<trial-id>.json`. Compare `--defense bound` with `each_hop`; also try TTL 1 or 60 with `--cache primed`. Each probe uses a unique trial hostname, so an empty cache really begins with a new name. The default resolver subnet is `10.217.53.0/24` with resolver IP `10.217.53.53`; set `SSRF_LAB_DNS_SUBNET` and `SSRF_LAB_RESOLVER_IP` together before building or running if this overlaps a local Docker network. The resolver adds 0.25 CPU, 128 MB, and 64 PIDs; the authority has the same runtime limits. No ports are published to the host.

If DNS probe cleanup is interrupted, remove only that instance using the same overlay files:

```bash
docker compose -f compose.yaml -f compose.measure.yaml -f compose.dns.yaml --project-name "ssrf-link-preview-${SSRF_LAB_INSTANCE}" down --remove-orphans
```

## Implementation and scope

`PreviewService` extracts HTML metadata after a `PageFetcher` retrieves a page. `RedirectingFetcher` handles the redirect loop and records ordered policy, connection, response, and failure events; `PycurlTransport` performs one HTTP request per hop. The browser demo defines per-trial defense and DNS settings in `demo/models.py`, address decisions in `demo/policy.py`, trial orchestration in `demo/controller.py`, and the trace-to-diagram projection in `demo/observations.py`. The lab services identify themselves in their responses, allowing the diagram to compare the actual peer with the claimed service and trial. A contradictory identity is flagged without changing the peer address or its network location. Trial IDs connect API responses, fetch traces, and lab service events. A transport timeout cannot prove that a target received the request, so the diagram marks delivery as unconfirmed.

Docker gives both lab zones private IPs, so the external lab service's address is an explicit experimental exception to public-IP classification. The always-on boundary permits only the two resolved lab service IPs as non-global destinations. This is a controlled reproduction, not a production SSRF filter or a claim that arbitrary public websites are safe to fetch. The browser demo's public egress also changes the proposal's originally offline testbed topology; the isolated baseline preserves that original property.

The repository includes an interactive demonstration, an automated redirect baseline, bounded repeated measurements for the listed offline scenarios, and a single-run recursive DNS probe. The probe is not yet a validated 100-repetition TTL/cache matrix. Controlled HTTPS fixtures, packet captures, and a `safehttpx` comparison remain to be implemented. Current `safehttpx` uses Google DNS as a fallback, while the offline lab has no Internet route and Docker-assigned external addresses are non-global; a fair comparison needs an explicit, documented address and resolver setup rather than silently whitelisting the attacker domain.

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
