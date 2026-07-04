import uuid
from typing import Optional


def get_or_create_request_id(request_headers: dict, *header_names: str) -> str:
    """Utility to get an existing request id from headers or generate a new one."""
    for name in header_names:
        if name in request_headers and request_headers.get(name):
            return str(request_headers.get(name))
    return str(uuid.uuid4())


def get_header(request_headers: dict, *header_names: str) -> Optional[str]:
    for name in header_names:
        v = request_headers.get(name)
        if v:
            return str(v)
    return None

