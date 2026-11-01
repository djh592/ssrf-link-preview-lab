"""Health check for the authority's loopback control endpoint."""

import json
from urllib.request import urlopen


def main() -> int:
    with urlopen("http://127.0.0.1:8053/health", timeout=2) as response:
        payload = json.load(response)
    return 0 if isinstance(payload.get("configured"), bool) else 1


if __name__ == "__main__":
    raise SystemExit(main())
