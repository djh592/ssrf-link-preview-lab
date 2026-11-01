"""Named fetching defenses shared by the demo and controlled experiments."""

from enum import StrEnum


class Defense(StrEnum):
    NONE = "none"
    INITIAL = "initial"
    EACH_HOP = "each_hop"
    BOUND = "bound"
    NO_REDIRECTS = "no_redirects"
