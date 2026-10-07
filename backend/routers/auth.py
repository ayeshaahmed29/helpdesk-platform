from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from core.audit import AuditAction, log_audit_event
from core.auth import get_current_user, get_token_payload
from core.token_denylist import revoke
from database import DbSession
from models.organization import Organization
from models.user import User, UserRole
from schemas.auth import LoginRequest, SignupRequest, TokenResponse, UserPublic
from security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


EMAIL_TAKEN = "An account with this email already exists"
INVALID_CREDENTIALS = "Invalid email or password"
DUMMY_HASH = hash_password("not-a-real-password")


@router.post("/signup", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: DbSession):
    email = payload.email.lower()

    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=EMAIL_TAKEN)

    organization = Organization(name=payload.organization_name)
    user = User(
        email=email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=UserRole.owner,
        organization=organization,
    )
    db.add(user)

    try:
        # flush first so the new organization and user have ids for the audit entry
        db.flush()
        log_audit_event(
            db,
            organization_id=user.organization_id,
            actor_user_id=user.id,
            action=AuditAction.user_signup,
            entity_type="user",
            entity_id=user.id,
            metadata={"role": user.role.value},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=EMAIL_TAKEN)

    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbSession):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))

    if user is None:
        # burn the same time as a real check so response time doesn't reveal unknown emails
        verify_password(payload.password, DUMMY_HASH)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS)

    if not verify_password(payload.password, user.hashed_password) or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS)

    log_audit_event(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        action=AuditAction.user_login,
        entity_type="user",
        entity_id=user.id,
    )
    db.commit()

    return TokenResponse(
        access_token=create_access_token(user.id),
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: Annotated[dict, Depends(get_token_payload)]):
    revoke(payload["jti"], payload["exp"])
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserPublic)
def me(user: Annotated[User, Depends(get_current_user)]):
    return user