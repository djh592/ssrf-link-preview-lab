# Development conventions

Write code, user-facing text, comments, and docstrings in English. Use names and type annotations to describe ordinary data flow; use documentation to explain contracts and constraints that are not apparent from the signature.

## Module boundaries

- `api/` translates HTTP requests and responses; it does not implement fetching policy.
- `preview/` creates preview metadata from fetched HTML.
- `fetching/` owns redirect handling, address-policy contracts, and single-hop transport.
- `lab/` contains the isolated external and internal services and their in-container probe client.
- `demo/` owns per-trial settings, address decisions, and controlled DNS answers. The preview API serves its browser interface directly; target selection remains in the browser.
- `experiments/` runs and records automated trials; event models, log parsing, trial records, and terminal output have separate modules.
- `scripts/` contains thin launchers that locate this checkout and call package-level commands.

Follow PEP 257 for Python docstrings:

- Add a module docstring when a module has a non-obvious responsibility or safety boundary. Do not add one merely to restate its filename.
- Document public protocols, services, and lifecycle objects where callers need to know their behavior, failure modes, or side effects.
- Document a method when its return value, exception behavior, resource ownership, or security implications are not clear from its name and types. Simple constructors, serializers, and thin HTTP handlers do not need docstrings.
- Start with a short imperative summary. Add a blank line and further explanation only when necessary. Use `Args`, `Returns`, and `Raises` sections for longer contracts, without repeating types already expressed in annotations.
- Use inline comments for non-obvious reasoning or implementation constraints, not to narrate each statement. Keep comments accurate when behavior changes.

In this lab, distinguish an observed HTTP connection from an address-policy decision and from the separate connection-stage DNS query. Do not describe the demo's lab-IP exception as a production public-IP filter or claim that libcurl made the second DNS query.

Run the checks before submitting changes:

```bash
uv run --no-sync ruff format --check .
uv run --no-sync ruff check .
uv run --no-sync ty check
uv run --no-sync pytest
```
