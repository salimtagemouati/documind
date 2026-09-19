from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared Limiter instance for SlowAPI route rate limiting
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
