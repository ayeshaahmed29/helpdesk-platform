from typing import Annotated

import jwt
from database import DbSession
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from models import User
from security import decode_access_token

from core.token_denylist import is_revoked

# auto_error=False lets us return a clean 401 ourselves when the header is missing
bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_token_payload(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> dict:
    """Validate the bearer token and return its claims. Used by logout and get_current_user."""
    if credentials is None:
        raise _unauthorized("Not authenticated")

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.InvalidTokenError:
        raise _unauthorized("Invalid or expired token")

    if "sub" not in payload or "jti" not in payload:
        raise _unauthorized("Invalid or expired token")

    if is_revoked(payload["jti"]):
        raise _unauthorized("Token has been revoked")

    return payload


def get_current_user(
    payload: Annotated[dict, Depends(get_token_payload)],
    db: DbSession,
) -> User:
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise _unauthorized("Invalid or expired token")

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized("Invalid or expired token")

    return user