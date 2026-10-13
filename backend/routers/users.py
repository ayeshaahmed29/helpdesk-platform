from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from core.audit import AuditAction, log_audit_event
from core.permissions import MANAGER_ROLES, ensure_same_org, require_role
from database import DbSession
from models import User
from models.user import UserRole
from schemas.users import UserAdminOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])

ManagerUser = Annotated[User, Depends(require_role(*MANAGER_ROLES))]


@router.get("", response_model=list[UserAdminOut])
def list_users(user: ManagerUser, db: DbSession):
    return db.scalars(
        select(User)
        .where(User.organization_id == user.organization_id)
        .order_by(User.created_at, User.id)
    ).all()


@router.patch("/{user_id}", response_model=UserAdminOut)
def update_user(user_id: int, payload: UserUpdate, user: ManagerUser, db: DbSession):
    # Same 404 and same message for "does not exist" and "other company",
    # so one company cannot learn which ids exist in another.
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    ensure_same_org(user, target.organization_id)

    role_changes = payload.role is not None and payload.role != target.role
    deactivating = payload.is_active is False and target.is_active
    reactivating = payload.is_active is True and not target.is_active

    # An admin cannot create or change an owner
    if user.role != UserRole.owner:
        if target.role == UserRole.owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only an owner can change an owner",
            )
        if payload.role == UserRole.owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only an owner can make someone an owner",
            )

    # Nobody can demote or deactivate themselves
    if target.id == user.id and (role_changes or deactivating):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot change your own role or deactivate yourself",
        )

    # The last active owner can never be demoted or deactivated.
    # The other active owners are locked while we count, so two requests at the
    # same moment cannot both remove an owner.
    if target.role == UserRole.owner and target.is_active and (role_changes or deactivating):
        other_active_owners = db.scalars(
            select(User.id)
            .where(
                User.organization_id == user.organization_id,
                User.role == UserRole.owner,
                User.is_active.is_(True),
                User.id != target.id,
            )
            .with_for_update()
        ).all()
        if not other_active_owners:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A company must always have at least one active owner",
            )

    changed = False

    if role_changes:
        old_role = target.role
        target.role = payload.role
        log_audit_event(
            db,
            organization_id=user.organization_id,
            actor_user_id=user.id,
            action=AuditAction.user_role_changed,
            entity_type="user",
            entity_id=target.id,
            metadata={"role": [old_role.value, payload.role.value]},
        )
        changed = True

    if deactivating:
        target.is_active = False
        log_audit_event(
            db,
            organization_id=user.organization_id,
            actor_user_id=user.id,
            action=AuditAction.user_deactivated,
            entity_type="user",
            entity_id=target.id,
            metadata={"is_active": [True, False]},
        )
        changed = True
    elif reactivating:
        target.is_active = True
        changed = True

    if changed:
        db.commit()
        db.refresh(target)

    return target