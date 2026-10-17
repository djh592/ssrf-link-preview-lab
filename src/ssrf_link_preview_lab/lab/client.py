import argparse
import json
from collections.abc import Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def probe_url(url: str, *, timeout_seconds: float) -> dict[str, object]:
    try:
        with urlopen(url, timeout=timeout_seconds) as response:
            return {
                "reachable": True,
                "status_code": response.status,
                "error": None,
            }
    except HTTPError as error:
        error.close()
        return {
            "reachable": True,
            "status_code": error.code,
            "error": str(error),
        }
    except (TimeoutError, URLError) as error:
        return {"reachable": False, "status_code": None, "error": str(error)}


def request_preview(url: str, *, timeout_seconds: float) -> dict[str, object]:
    request = Request(
        "http://127.0.0.1:8000/preview",
        data=json.dumps({"url": url}).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return {
                "ok": True,
                "status_code": response.status,
                "body": _decode_json(response.read()),
                "error": None,
            }
    except HTTPError as error:
        try:
            body = _decode_json(error.read())
        finally:
            error.close()
        return {
            "ok": False,
            "status_code": error.code,
            "body": body,
            "error": str(error),
        }
    except (TimeoutError, URLError) as error:
        return {
            "ok": False,
            "status_code": None,
            "body": None,
            "error": str(error),
        }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Client for isolated lab services")
    parser.add_argument("operation", choices=("preview", "probe", "health"))
    parser.add_argument("url")
    parser.add_argument("--timeout", type=float, default=15.0)
    arguments = parser.parse_args(argv)
    if arguments.timeout <= 0:
        parser.error("--timeout must be positive")

    if arguments.operation == "preview":
        result = request_preview(arguments.url, timeout_seconds=arguments.timeout)
    else:
        result = probe_url(arguments.url, timeout_seconds=arguments.timeout)
    print(json.dumps(result, sort_keys=True))
    if arguments.operation == "health" and result["reachable"] is not True:
        return 1
    return 0


def _decode_json(body: bytes) -> object:
    try:
        return json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Lab service returned an invalid JSON response") from error


if __name__ == "__main__":
    raise SystemExit(main())
