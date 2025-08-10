import json


def sse(event: str, data: dict | str) -> str:
    """Format a Server-Sent Event line block."""
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"event: {event}\n" f"data: {payload}\n\n"

def heartbeat() -> str:
    """Comment line to keep connection alive."""
    return ": ping\n\n"