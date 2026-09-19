from jose import JWTError, jwt
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

settings = get_settings()


def exempt_non_demo_request(request) -> bool:
    """Only valid public-demo JWTs consume the strict per-IP AI budget."""
    authorization = request.headers.get("authorization", "")
    if not authorization.lower().startswith("bearer "):
        return True
    try:
        payload = jwt.decode(
            authorization.split(" ", 1)[1],
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except (JWTError, IndexError):
        return True
    return not bool(payload.get("is_demo"))

# Shared Limiter instance for SlowAPI route rate limiting
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
