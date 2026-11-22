"""Classify a generated preview from recorded response evidence."""

from collections.abc import Sequence
from enum import StrEnum

from ssrf_link_preview_lab.demo.observations import ObservedRequest


class PreviewKind(StrEnum):
    """Presentation category supported by the final page-response evidence."""

    STANDARD = "standard"
    RESTRICTED = "restricted"
    UNVERIFIED = "unverified"
    UNAVAILABLE = "unavailable"


def classify_preview(
    *, generated: bool, page_observations: Sequence[ObservedRequest]
) -> PreviewKind:
    """Classify the preview without inferring identity from its URL or metadata."""
    if not generated:
        return PreviewKind.UNAVAILABLE

    responses = tuple(
        observation
        for observation in page_observations
        if observation.outcome == "responded"
    )
    if not responses:
        return PreviewKind.UNVERIFIED

    final_response = responses[-1]
    if final_response.identity_matches is False:
        return PreviewKind.UNVERIFIED
    if (
        final_response.destination == "internal-report"
        and final_response.responder_service == "internal-report"
        and final_response.identity_matches is True
    ):
        return PreviewKind.RESTRICTED
    return PreviewKind.STANDARD
