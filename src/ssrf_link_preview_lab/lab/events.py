from fastapi import Request

from ssrf_link_preview_lab.tracing import (
    RESPONDER_SERVICE_HEADER,
    RESPONDER_TRIAL_HEADER,
    TRIAL_ID_HEADER,
    write_structured_event,
)


def request_trial_id(request: Request) -> str | None:
    return request.headers.get(TRIAL_ID_HEADER)


def observation_headers(request: Request, service: str) -> dict[str, str]:
    headers = {RESPONDER_SERVICE_HEADER: service}
    if trial_id := request_trial_id(request):
        headers[RESPONDER_TRIAL_HEADER] = trial_id
    return headers


def write_event(
    event: str,
    request: Request,
    *,
    trial_id: str | None,
    **fields: object,
) -> None:
    client_host = request.client.host if request.client is not None else None
    write_structured_event(
        event,
        trial_id=trial_id,
        client_host=client_host,
        **fields,
    )
