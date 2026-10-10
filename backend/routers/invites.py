import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from core.audit import AuditAction, log_audit_event
from core.email import EmailSendError, send_email
from core.permissions import MANAGER_ROLES, require_role
from database import DbSession
from models import Invite, Organization, User
from models.user import UserRole
from schemas.auth import UserPublic
from schemas.invites import (
    AcceptInviteRequest,
    InviteCreate,
    InviteOut,
    InvitePreview,
)
from security import hash_password

router = APIRouter(prefix="/invites", tags=["invites"])

ManagerUser = Annotated[User, Depends(require_role(*MANAGER_ROLES))]

INVITE_VALID_DAYS = 7


def hash_token(token: str) -> str:
    """Only this hash is stored. The real token exists only in the email link."""
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _invite_status(invite: Invite) -> str:
    if invite.accepted_at is not None:
        return "accepted"
    if invite.expires_at <= _now():
        return "expired"
    return "pending"


def _to_out(invite: Invite) -> InviteOut:
    return InviteOut(
        id=invite.id,
        email=invite.email,
        role=invite.role,
        status=_invite_status(invite),
        invited_by=invite.invited_by,
        expires_at=invite.expires_at,
        accepted_at=invite.accepted_at,
        created_at=invite.created_at,
    )


def _get_usable_invite(db: DbSession, token: str, *, lock: bool = False) -> Invite:
    """Find an invite by its token. 404 if unknown, 410 if used or expired."""
    stmt = select(Invite).where(Invite.token_hash == hash_token(token))
    if lock:
        # lock the row so two accepts at the same moment cannot both succeed
        stmt = stmt.with_for_update()
    invite = db.scalar(stmt)

    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
    if invite.accepted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE, detail="This invite has already been used"
        )
    if invite.expires_at <= _now():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This invite has expired")
    return invite


@router.post("", response_model=InviteOut, status_code=status.HTTP_201_CREATED)
def create_invite(payload: InviteCreate, user: ManagerUser, db: DbSession):
    if payload.role == UserRole.owner and user.role != UserRole.owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an owner can invite another owner",
        )

    email = payload.email.lower()

    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    pending_id = db.scalar(
        select(Invite.id).where(
            Invite.organization_id == user.organization_id,
            Invite.email == email,
            Invite.accepted_at.is_(None),
            Invite.expires_at > _now(),
        )
    )
    if pending_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email already has a pending invite",
        )

    token = secrets.token_urlsafe(32)
    invite = Invite(
        email=email,
        role=payload.role.value,
        organization_id=user.organization_id,
        invited_by=user.id,
        token_hash=hash_token(token),
        expires_at=_now() + timedelta(days=INVITE_VALID_DAYS),
    )
    db.add(invite)
    db.flush()  # gives the invite an id for the audit entry

    log_audit_event(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        action=AuditAction.invite_created,
        entity_type="invite",
        entity_id=invite.id,
        metadata={"role": invite.role},
    )

    organization = db.get(Organization, user.organization_id)
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    link = f"{frontend_url}/accept-invite/{token}"
    inviter = user.full_name or user.email
    body = (
        f"{inviter} invited you to join {organization.name} on Helpdesk "
        f"as {invite.role}.\n\n"
        f"Open this link to create your account:\n"
        f"{link}\n\n"
        f"The link works for {INVITE_VALID_DAYS} days and can be used once."
    )

    try:
        send_email(invite.email, f"You are invited to join {organization.name}", body)
    except EmailSendError as exc:
        # nothing is saved, so the manager can simply try again
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not send the invite email. Please try again.",
        ) from exc

    db.commit()
    db.refresh(invite)
    return _to_out(invite)


@router.get("", response_model=list[InviteOut])
def list_invites(user: ManagerUser, db: DbSession):
    invites = db.scalars(
        select(Invite)
        .where(Invite.organization_id == user.organization_id)
        .order_by(Invite.created_at.desc(), Invite.id.desc())
    ).all()
    return [_to_out(invite) for invite in invites]


@router.get("/{token}", response_model=InvitePreview)
def get_invite(token: str, db: DbSession):
    invite = _get_usable_invite(db, token)
    organization = db.get(Organization, invite.organization_id)
    return InvitePreview(
        email=invite.email,
        role=invite.role,
        organization_name=organization.name,
        expires_at=invite.expires_at,
    )


@router.post(
    "/{token}/accept", response_model=UserPublic, status_code=status.HTTP_201_CREATED
)
def accept_invite(token: str, payload: AcceptInviteRequest, db: DbSession):
    invite = _get_usable_invite(db, token, lock=True)

    if db.scalar(select(User.id).where(User.email == invite.email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        email=invite.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=UserRole(invite.role),
        organization_id=invite.organization_id,
    )
    db.add(user)
    invite.accepted_at = _now()

    try:
        db.flush()  # gives the new user an id for the audit entry
        log_audit_event(
            db,
            organization_id=invite.organization_id,
            actor_user_id=user.id,
            action=AuditAction.invite_accepted,
            entity_type="invite",
            entity_id=invite.id,
            metadata={"role": invite.role},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from exc

    db.refresh(user)
    return user