"""Run browser-demo trials with one operator-controlled state."""

import socket
from threading import Lock
from uuid import uuid4

from ssrf_link_preview_lab.demo.dns import DemoDNS
from ssrf_link_preview_lab.demo.models import DemoState, DNSMode
from ssrf_link_preview_lab.demo.policy import DemoAddressPolicy
from ssrf_link_preview_lab.fetching.errors import FetchError
from ssrf_link_preview_lab.fetching.redirecting import RedirectingFetcher
from ssrf_link_preview_lab.preview.errors import UnsupportedContentTypeError
from ssrf_link_preview_lab.preview.service import PreviewService
from ssrf_link_preview_lab.tracing import write_structured_event

EXTERNAL_URL = "http://external-page:8080/page"
INTERNAL_URL = "http://internal-report:8080/report"
REBIND_URL = "http://rebind.lab:8080/report"
REDIRECT_PAGE_URL = "http://external-page:8080/redirect/page"
REDIRECT_INTERNAL_URL = "http://external-page:8080/redirect/internal"
PUBLIC_URL = "https://www.python.org/"


class DemoController:
    def __init__(self) -> None:
        self._lock = Lock()
        self._state = DemoState()
        self._dns = DemoDNS()

    def state(self) -> dict[str, object]:
        with self._lock:
            return self._state_payload()

    def configure(self, state: DemoState) -> dict[str, object]:
        with self._lock:
            self._state = state
            return self._state_payload()

    def _state_payload(self) -> dict[str, object]:
        return {
            **self._state.to_dict(),
            "urls": {
                "page": EXTERNAL_URL,
                "internal": INTERNAL_URL,
                "redirect_page": REDIRECT_PAGE_URL,
                "redirect_internal": REDIRECT_INTERNAL_URL,
                "rebind": REBIND_URL,
                "public": PUBLIC_URL,
            },
        }

    def run(self, url: str) -> dict[str, object]:
        with self._lock:
            trial_id = uuid4()
            result: dict[str, object]
            self._dns.configure("", "", rebind=False)
            try:
                external_ip = socket.gethostbyname("external-page")
                internal_ip = socket.gethostbyname("internal-report")
                self._dns.configure(
                    external_ip,
                    internal_ip,
                    rebind=self._state.dns_mode is DNSMode.REBIND,
                )
                policy = DemoAddressPolicy(
                    self._state.defense, external_ip, internal_ip, self._dns
                )
                service = PreviewService(RedirectingFetcher(address_policy=policy))
                preview = service.create(url, trial_id=trial_id)
            except (
                FetchError,
                UnsupportedContentTypeError,
                OSError,
                RuntimeError,
            ) as error:
                trace = error.trace.to_dict() if isinstance(error, FetchError) else {}
                result = {
                    "ok": False,
                    "trial_id": str(trial_id),
                    "message": str(error),
                    "trace": trace,
                }
            else:
                result = {
                    "ok": True,
                    "trial_id": str(trial_id),
                    "requested_url": preview.requested_url,
                    "final_url": preview.final_url,
                    "title": preview.title,
                    "description": preview.description,
                    "site_name": preview.site_name,
                    "image_data_url": preview.image_data_url,
                    "trace": preview.trace.to_dict(),
                    "image_trace": preview.image_trace.to_dict(),
                }
            result["dns_answers"] = [answer.to_dict() for answer in self._dns.answers]
            result["defense"] = self._state.defense.value
            result["dns_mode"] = self._state.dns_mode.value
            write_structured_event("demo_trial", trial_id=trial_id, result=result)
            return result

    def close(self) -> None:
        self._dns.close()
