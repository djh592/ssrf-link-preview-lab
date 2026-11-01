"""Run browser-demo trials using one shared loopback DNS authority."""

import socket
from threading import Lock
from uuid import uuid4

from ssrf_link_preview_lab.demo.dns import DemoDNS
from ssrf_link_preview_lab.demo.models import Defense, DNSMode, TrialConfiguration
from ssrf_link_preview_lab.demo.observations import LabAddresses, project_observations
from ssrf_link_preview_lab.demo.policy import DemoAddressPolicy
from ssrf_link_preview_lab.fetching.models import FetchTrace
from ssrf_link_preview_lab.fetching.redirecting import RedirectingFetcher, RedirectMode
from ssrf_link_preview_lab.preview.service import PreviewService
from ssrf_link_preview_lab.tracing import write_structured_event
from ssrf_link_preview_lab.trials.execution import execute_preview

EXTERNAL_URL = "http://external-page:8080/page"
INTERNAL_URL = "http://internal-report:8080/report"
REBIND_URL = "http://rebind.lab:8080/report"
REDIRECT_PAGE_URL = "http://external-page:8080/redirect/page"
REDIRECT_INTERNAL_URL = "http://external-page:8080/redirect/internal"
PUBLIC_URL = "https://www.python.org/"


class DemoController:
    def __init__(self) -> None:
        self._lock = Lock()
        self._dns = DemoDNS()

    @staticmethod
    def setup() -> dict[str, object]:
        """Return immutable options needed to prepare a browser trial."""
        return {
            "defaults": TrialConfiguration().to_dict(),
            "targets": {
                "page": EXTERNAL_URL,
                "internal": INTERNAL_URL,
                "redirect_page": REDIRECT_PAGE_URL,
                "redirect_internal": REDIRECT_INTERNAL_URL,
                "rebind": REBIND_URL,
                "public": PUBLIC_URL,
            },
        }

    def run(self, url: str, configuration: TrialConfiguration) -> dict[str, object]:
        """Run a trial with the exact settings supplied in its request."""
        with self._lock:
            trial_id = uuid4()
            result: dict[str, object]
            page_trace = FetchTrace()
            image_trace = FetchTrace()
            lab: LabAddresses | None = None
            self._dns.configure("", "", rebind=False)
            try:
                external_ip = socket.gethostbyname("external-page")
                internal_ip = socket.gethostbyname("internal-report")
                lab = LabAddresses(external_ip, internal_ip)
                self._dns.configure(
                    external_ip,
                    internal_ip,
                    rebind=configuration.dns_mode is DNSMode.REBIND,
                )
                policy = DemoAddressPolicy(
                    configuration.defense, external_ip, internal_ip, self._dns
                )
                service = PreviewService(
                    RedirectingFetcher(
                        address_policy=policy,
                        redirect_mode=(
                            RedirectMode.STOP
                            if configuration.defense is Defense.NO_REDIRECTS
                            else RedirectMode.FOLLOW
                        ),
                    )
                )
                execution = execute_preview(service, url, trial_id=trial_id)
            except (OSError, RuntimeError) as error:
                result = {
                    "ok": False,
                    "trial_id": str(trial_id),
                    "requested_url": url,
                    "message": str(error),
                }
            else:
                page_trace = execution.trace
                if execution.preview is not None:
                    image_trace = execution.preview.image_trace
                result = execution.to_dict()
            result.setdefault("trace", page_trace.to_dict())
            result.setdefault("image_trace", image_trace.to_dict())
            result["observations"] = (
                [
                    step.to_dict()
                    for trace, resource in (
                        (page_trace, "page"),
                        (image_trace, "image"),
                    )
                    for step in project_observations(
                        trace, resource=resource, trial_id=trial_id, lab=lab
                    )
                ]
                if lab is not None
                else []
            )
            result["dns_answers"] = [answer.to_dict() for answer in self._dns.answers]
            result["configuration"] = configuration.to_dict()
            write_structured_event("demo_trial", trial_id=trial_id, result=result)
            return result

    def close(self) -> None:
        self._dns.close()
