# SSRF Link Preview Lab

A controlled testbed for evaluating server-side request forgery (SSRF) defenses
in a link preview service. The project compares where address validation occurs
and whether the HTTP client connects to the address that was actually checked.

## Safety

This repository contains an intentionally unfiltered fetching policy for use as
an experimental baseline. It can reach services available to the machine that
runs it. Do not expose the application to untrusted users, run it on a cloud
host, or use it outside an isolated and authorized lab network.

Network fetching is disabled by default. It must be enabled explicitly for a
controlled experiment.

## Security question and threat model

The experiments ask how the placement of address checks, and whether a client
connects to the checked address, affect SSRF protection when redirects and
changing DNS answers are present.

The attacker may submit preview URLs, control external pages and redirects, and
choose DNS answers for a domain they own. They cannot modify the preview
service, resolver configuration, or internal report service. The primary
security goal is that a submitted preview task must not send an HTTP request to
the internal service. Returning an internal marker in a preview is measured
separately as data disclosure.

## Architecture

The implementation currently follows this dependency direction:

```text
FastAPI route -> PreviewService -> PageFetcher contract
                                      |-> DisabledFetcher
                                      `-> PycurlFetcher (unfiltered baseline)
```

The API translates HTTP input and expected failures. `PreviewService` owns the
preview use case and HTML metadata parsing. Fetchers own network behavior. This
keeps future validation and address-binding policies out of the API layer and
allows each policy to share the same preview behavior.

## Current scope

The current implementation provides:

- a FastAPI application with health and link preview endpoints;
- an explicit `disabled` default and an `unfiltered` experimental policy;
- HTTP(S)-only, IPv4-only fetching through PycURL/libcurl;
- a 10-second total timeout, 1 MB decoded-body limit, and 5-redirect limit;
- TLS certificate verification for HTTPS requests;
- HTML title and description extraction, including Open Graph metadata;
- unit and local integration tests that do not contact the public Internet.

Address validation, checked-address binding, trace collection, the isolated
network testbed, DNS rebinding scenarios, and the experiment runner are planned
but not implemented yet.

## Development

Install the locked project environment:

```bash
uv sync --locked
```

Run the API with fetching disabled:

```bash
uv run --no-sync fastapi dev src/ssrf_link_preview_lab/api/app.py
```

To exercise the deliberately unfiltered policy in an isolated lab:

```bash
SSRF_LAB_FETCH_POLICY=unfiltered \
  uv run --no-sync fastapi dev src/ssrf_link_preview_lab/api/app.py
```

Submit a preview request:

```bash
curl --request POST http://127.0.0.1:8000/preview \
  --header 'content-type: application/json' \
  --data '{"url":"http://controlled-page.example/"}'
```

`controlled-page.example` is a placeholder and must be replaced with a service
inside the isolated lab network.

The interactive API documentation is available at
`http://127.0.0.1:8000/docs` while the service is running.

## Quality checks

```bash
uv run --no-sync ruff format --check .
uv run --no-sync ruff check .
uv run --no-sync ty check
uv run --no-sync pytest
```

Ruff, ty, and pytest are the complete development quality toolchain. No warning
or error is suppressed merely to make these commands pass.
