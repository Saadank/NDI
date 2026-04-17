from fastapi import Request


def client_ip(request: Request) -> str | None:
    """Return the client IP address for audit purposes.

    Prefer the first token of X-Forwarded-For (valid only when nginx/a trusted
    proxy is in front); fall back to request.client.host for direct connections.
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    if request.client:
        return request.client.host
    return None


def user_agent(request: Request, max_len: int = 512) -> str | None:
    ua = request.headers.get("user-agent")
    if not ua:
        return None
    return ua[:max_len]
