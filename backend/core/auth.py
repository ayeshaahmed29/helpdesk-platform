from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from database import get_db
from models import User

bearer_scheme = HTTPBearer()

FAKE_TOKEN_PREFIX = "fake-"


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    # Temporary fake auth until Ayesha's real login is ready.
    # Send the header "Authorization: Bearer fake-<user_id>", e.g. "fake-1".
    token = credentials.credentials
    user_id = token.removeprefix(FAKE_TOKEN_PREFIX)

    if not token.startswith(FAKE_TOKEN_PREFIX) or not user_id.isdigit():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.get(User, int(user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user