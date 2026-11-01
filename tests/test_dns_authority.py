import json
from uuid import UUID

import dns.message
import dns.rdatatype
import pytest
from pytest import CaptureFixture

from ssrf_link_preview_lab.experiments.event_models import DNSAuthorityAnswer
from ssrf_link_preview_lab.experiments.event_parser import parse_trial_events
from ssrf_link_preview_lab.lab.dns_authority import AuthorityState

_TRIAL_ID = UUID("1a2b3c4d-0000-4000-8000-000000000001")
_EXTERNAL = "172.23.0.4"
_INTERNAL = "172.24.0.4"


@pytest.mark.parametrize("ttl", [0, 1, 60])
def test_authority_records_rebinding_answers(
    ttl: int, capsys: CaptureFixture[str]
) -> None:
    state = AuthorityState()
    state.configure(_EXTERNAL, _INTERNAL)
    hostname = f"t{_TRIAL_ID.hex}.rebind.ttl{ttl}.attack.lab"
    query = dns.message.make_query(hostname, dns.rdatatype.A)

    first = state.answer(query)
    second = state.answer(query)

    assert first.answer[0][0].to_text() == _EXTERNAL
    assert second.answer[0][0].to_text() == _INTERNAL
    assert first.answer[0].ttl == ttl
    assert second.answer[0].ttl == ttl
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [event["query"] for event in events] == [1, 2]
    assert all(event["trial_id"] == str(_TRIAL_ID) for event in events)
    parsed = parse_trial_events(
        "dns-authority",
        "\n".join(json.dumps(event) for event in events),
        trial_id=_TRIAL_ID,
    )
    assert all(isinstance(event.details, DNSAuthorityAnswer) for event in parsed)
    assert [
        event.details.address
        for event in parsed
        if isinstance(event.details, DNSAuthorityAnswer)
    ] == [_EXTERNAL, _INTERNAL]


def test_authority_uses_independent_trial_names() -> None:
    state = AuthorityState()
    state.configure(_EXTERNAL, _INTERNAL)
    first_name = f"t{_TRIAL_ID.hex}.rebind.ttl0.attack.lab"
    second_name = f"t{UUID(int=2).hex}.rebind.ttl0.attack.lab"

    state.answer(dns.message.make_query(first_name, dns.rdatatype.A))
    response = state.answer(dns.message.make_query(second_name, dns.rdatatype.A))

    assert response.answer[0][0].to_text() == _EXTERNAL


def test_non_a_query_does_not_advance_rebinding_sequence() -> None:
    state = AuthorityState()
    state.configure(_EXTERNAL, _INTERNAL)
    hostname = f"t{_TRIAL_ID.hex}.rebind.ttl0.attack.lab"

    response = state.answer(dns.message.make_query(hostname, dns.rdatatype.AAAA))
    first_a = state.answer(dns.message.make_query(hostname, dns.rdatatype.A))

    assert response.answer == []
    assert first_a.answer[0][0].to_text() == _EXTERNAL
