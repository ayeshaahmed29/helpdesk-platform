import os
import time

import redis
from fastapi import HTTPException

_r = redis.Redis.from_url(
    os.environ["REDIS_URL"],
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)

def _unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail="Authentication service temporarily unavailable")

def revoke(jti: str, exp: int) -> None:
    ttl = max(int(exp - time.time()), 1)
    try:
        _r.set(f"revoked:{jti}", "1", ex=ttl)
    except redis.RedisError:
        raise _unavailable()

def is_revoked(jti: str) -> bool:
    try:
        return _r.exists(f"revoked:{jti}") == 1
    except redis.RedisError:
        raise _unavailable()