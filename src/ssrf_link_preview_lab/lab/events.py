from fastapi import Request

from ssrf_link_preview_lab.tracing import TRIAL_ID_HEADER, write_structured_event


def request_trial_id(request: Request) -> str | None:
    return request.headers.get(TRIAL_ID_HEADER)


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
