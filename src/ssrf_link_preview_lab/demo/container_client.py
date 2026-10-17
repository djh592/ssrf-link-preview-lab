"""Call the demo API from inside the isolated preview container."""

import argparse
import json
from collections.abc import Sequence
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

_ROUTES = {
    ("GET", "/demo/state"),
    ("PUT", "/demo/state"),
    ("POST", "/demo/trial"),
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Call the isolated demo API")
    parser.add_argument("method", choices=("GET", "PUT", "POST"))
    parser.add_argument("path", choices=("/demo/state", "/demo/trial"))
    parser.add_argument("body", nargs="?", default="")
    arguments = parser.parse_args(argv)
    if (arguments.method, arguments.path) not in _ROUTES:
        parser.error("Unsupported demo operation")

    request = Request(
        f"http://127.0.0.1:8000{arguments.path}",
        data=arguments.body.encode() if arguments.method != "GET" else None,
        headers={"Content-Type": "application/json"},
        method=arguments.method,
    )
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(request, timeout=15.0) as response:
            payload = _envelope(response.status, response.read())
    except HTTPError as error:
        try:
            payload = _envelope(error.code, error.read())
        finally:
            error.close()
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _envelope(status_code: int, body: bytes) -> dict[str, object]:
    return {"status_code": status_code, "body": json.loads(body)}


if __name__ == "__main__":
    raise SystemExit(main())
