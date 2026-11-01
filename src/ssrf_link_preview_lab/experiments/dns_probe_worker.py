"""Exercise one real DNS check-to-connection sequence inside Preview."""

import argparse
import json
import socket
from collections.abc import Sequence
from urllib.parse import urlsplit
from uuid import UUID

from ssrf_link_preview_lab.experiments.policy import LabAddressPolicy, RecursiveResolver
from ssrf_link_preview_lab.fetching.redirecting import RedirectingFetcher
from ssrf_link_preview_lab.fetching.strategies import Defense
from ssrf_link_preview_lab.preview.service import PreviewService
from ssrf_link_preview_lab.trials.execution import execute_preview


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe real recursive DNS behavior")
    parser.add_argument("trial_id", type=UUID)
    parser.add_argument(
        "--mode", choices=("external", "internal", "rebind"), default="rebind"
    )
    parser.add_argument("--ttl", type=int, choices=(0, 1, 60), default=0)
    parser.add_argument("--cache", choices=("empty", "primed"), default="empty")
    parser.add_argument(
        "--defense",
        type=Defense,
        choices=(Defense.EACH_HOP, Defense.BOUND),
        default=Defense.EACH_HOP,
    )
    arguments = parser.parse_args(argv)
    if arguments.cache == "primed" and (
        arguments.mode != "rebind" or arguments.ttl == 0
    ):
        parser.error("A primed external answer requires rebinding with TTL 1 or 60")

    hostname = (
        f"t{arguments.trial_id.hex}.{arguments.mode}.ttl{arguments.ttl}.attack.lab"
    )
    url = f"http://{hostname}:8080/report"
    external_ip = socket.gethostbyname("external-page")
    resolver = RecursiveResolver()
    if arguments.cache == "primed":
        resolver.resolve(urlsplit(url).hostname or hostname, 2.0)
    service = PreviewService(
        RedirectingFetcher(
            address_policy=LabAddressPolicy(arguments.defense, external_ip, resolver)
        ),
        fetch_images=False,
    )
    execution = execute_preview(service, url, trial_id=arguments.trial_id)
    print(
        json.dumps(
            {
                "mode": arguments.mode,
                "ttl": arguments.ttl,
                "cache": arguments.cache,
                "defense": arguments.defense,
                "hostname": hostname,
                "external_ip": external_ip,
                "execution": execution.to_dict(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
