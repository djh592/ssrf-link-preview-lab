"""Run one measured preview inside the isolated preview container."""

import argparse
import json
import socket
from collections.abc import Sequence
from uuid import UUID

from ssrf_link_preview_lab.experiments.policy import LabAddressPolicy
from ssrf_link_preview_lab.experiments.scenarios import Scenario, case_for
from ssrf_link_preview_lab.fetching.redirecting import RedirectingFetcher, RedirectMode
from ssrf_link_preview_lab.fetching.strategies import Defense
from ssrf_link_preview_lab.preview.service import PreviewService
from ssrf_link_preview_lab.trials.execution import execute_preview


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one offline preview trial")
    parser.add_argument("scenario", type=Scenario, choices=list(Scenario))
    parser.add_argument("defense", type=Defense, choices=list(Defense))
    parser.add_argument("trial_id", type=UUID)
    arguments = parser.parse_args(argv)

    external_ip = socket.gethostbyname("external-page")
    internal_ip = socket.gethostbyname("internal-report")
    case = case_for(arguments.scenario, internal_ip=internal_ip)
    policy = LabAddressPolicy(arguments.defense, external_ip)
    fetcher = RedirectingFetcher(
        address_policy=policy,
        redirect_mode=(
            RedirectMode.STOP
            if arguments.defense is Defense.NO_REDIRECTS
            else RedirectMode.FOLLOW
        ),
    )
    execution = execute_preview(
        PreviewService(fetcher, fetch_images=False),
        case.target_url,
        trial_id=arguments.trial_id,
    )
    print(json.dumps(execution.to_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
