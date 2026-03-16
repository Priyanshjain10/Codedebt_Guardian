from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def _get_real_client_ip(request: Request) -> str:
    """Extract real client IP, respecting X-Forwarded-For from trusted proxies."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP (original client), not the proxy's IP
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return get_remote_address(request)


def _get_user_or_ip_key(request: Request) -> str:
    """Rate limit by user ID when authenticated, fall back to IP for anonymous."""
    # Try to get user ID from JWT token claims stored in request state
    user = getattr(request.state, "user", None)
    if user and hasattr(user, "id"):
        return f"user:{user.id}"
    # Fall back to real client IP
    return _get_real_client_ip(request)


# Global rate limiter instance — uses user ID when authenticated, IP otherwise
limiter = Limiter(key_func=_get_user_or_ip_key)
