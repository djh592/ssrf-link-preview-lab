"""Configure the loopback-only control endpoint inside the DNS authority container."""

import argparse
import json
from collections.abc import Sequence
from urllib.request import Request, urlopen


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Configure the lab DNS authority")
    parser.add_argument("external_ip")
    parser.add_argument("internal_ip")
    arguments = parser.parse_args(argv)
    request = Request(
        "http://127.0.0.1:8053/configure",
        data=json.dumps(
            {"external": arguments.external_ip, "internal": arguments.internal_ip}
        ).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=3) as response:
        print(response.read().decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
