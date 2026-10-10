import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from core.audit import AuditAction, log_audit_event
from core.auth import get_current_user, get_token_payload
from core.email import EmailSendError, send_email
from core.token_denylist import revoke
from database import DbSession
from models.organization import Organization
from models.password_reset_token import PasswordResetToken
from models.user import User, UserRole
from schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    ResetPasswordRequest,
    SignupRequest,
    TokenResponse,
    UserPublic,
)
from security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

logger = logging.getLogger("uvicorn.error")

EMAIL_TAKEN = "An account with this email already exists"
INVALID_CREDENTIALS = "Invalid email or password"
DUMMY_HASH = hash_password("not-a-real-password")

RESET_VALID_MINUTES = 60
# The same text is returned whether or not the email exists
FORGOT_PASSWORD_MESSAGE = (
    "If an account with this email exists, we have sent a link to reset the password."
)


def _hash_token(token: str) -> str:
    """Only this hash is stored. The real token exists only in the email link."""
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _send_reset_email(to: str, link: str) -> None:
    """Runs after the response is sent, so the response time is the same for every email."""
    body = (
        "We received a request to reset your Helpdesk password.\n\n"
        "Open this link to choose a new password:\n"
        f"{link}\n\n"
        f"The link works for {RESET_VALID_MINUTES} minutes and can be used once.\n"
        "If you did not ask for this, you can ignore this email."
    )
    try:
        send_email(to, "Reset your Helpdesk password", body)
    except EmailSendError:
        # the user can simply ask again; the response must not reveal this
        logger.error("Password reset email could not be sent")


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


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def forgot_password(
    payload: ForgotPasswordRequest, background_tasks: BackgroundTasks, db: DbSession
):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))

    # Unknown or inactive email: do nothing, and return the same response as a real one
    if user is not None and user.is_active:
        token = secrets.token_urlsafe(32)
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=_hash_token(token),
                expires_at=_now() + timedelta(minutes=RESET_VALID_MINUTES),
            )
        )
        log_audit_event(
            db,
            organization_id=user.organization_id,
            actor_user_id=user.id,
            action=AuditAction.user_password_reset_requested,
            entity_type="user",
            entity_id=user.id,
        )
        db.commit()

        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
        background_tasks.add_task(
            _send_reset_email, user.email, f"{frontend_url}/reset-password/{token}"
        )

    return MessageResponse(message=FORGOT_PASSWORD_MESSAGE)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: DbSession):
    # lock the row so two requests at the same moment cannot both use the token
    reset = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == _hash_token(payload.token))
        .with_for_update()
    )

    if reset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reset link not found")
    if reset.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE, detail="This reset link has already been used"
        )
    if reset.expires_at <= _now():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This reset link has expired")

    user = db.get(User, reset.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_410_GONE, detail="This reset link is no longer valid"
        )

    now = _now()
    user.hashed_password = hash_password(payload.new_password)
    reset.used_at = now
    # any other reset link of this user stops working too
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.id != reset.id,
        )
        .values(used_at=now)
    )

    log_audit_event(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        action=AuditAction.user_password_reset,
        entity_type="user",
        entity_id=user.id,
    )
    db.commit()

    return MessageResponse(message="Your password has been changed. You can now log in.")