from dataclasses import dataclass, field

import pytest

from ssrf_link_preview_lab.experiments.policy import LabAddressPolicy
from ssrf_link_preview_lab.fetching.strategies import Defense

_EXTERNAL = "172.28.0.4"
_INTERNAL = "172.29.0.4"
_URL = "http://attacker.attack.lab:8080/report"


@dataclass
class _Resolver:
    answers: tuple[str, ...]
    calls: list[str] = field(default_factory=list)

    def resolve(self, hostname: str, timeout_seconds: float) -> tuple[str, ...]:
        self.calls.append(hostname)
        return self.answers


@pytest.mark.parametrize(
    ("defense", "sequence", "expected_checks", "bound"),
    [
        (Defense.NONE, 0, 0, False),
        (Defense.INITIAL, 0, 1, False),
        (Defense.INITIAL, 1, 0, False),
        (Defense.EACH_HOP, 1, 1, False),
        (Defense.BOUND, 1, 1, True),
        (Defense.NO_REDIRECTS, 0, 1, True),
    ],
)
def test_policy_checks_without_binding_unbound_connections(
    defense: Defense, sequence: int, expected_checks: int, bound: bool
) -> None:
    resolver = _Resolver((_EXTERNAL,))

    decisions, binding = LabAddressPolicy(defense, _EXTERNAL, resolver).prepare(
        _URL, sequence, 2.0
    )

    assert len(resolver.calls) == expected_checks
    assert len(decisions) == expected_checks
    assert (binding is not None) is bound
    if binding is not None:
        assert binding.address == _EXTERNAL
        assert binding.port == 8080


def test_policy_rejects_any_internal_answer_without_connecting() -> None:
    resolver = _Resolver((_EXTERNAL, _INTERNAL))

    decisions, binding = LabAddressPolicy(Defense.BOUND, _EXTERNAL, resolver).prepare(
        _URL, 0, 2.0
    )

    assert not decisions[0].allowed
    assert decisions[0].resolved_addresses == (_EXTERNAL, _INTERNAL)
    assert binding is None
