from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from core.audit import AuditAction
from core.permissions import MANAGER_ROLES, require_role
from database import DbSession
from models import AuditLog, User
from schemas.audit_logs import AuditLogItem, AuditLogPage

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])

ManagerUser = Annotated[User, Depends(require_role(*MANAGER_ROLES))]


def _start_of_day(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=timezone.utc)


@router.get("", response_model=AuditLogPage)
def list_audit_logs(
    user: ManagerUser,
    db: DbSession,
    action: Annotated[AuditAction | None, Query()] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=400, detail="date_from must not be after date_to"
        )

    # The company filter is always first and never comes from the request.
    conditions = [AuditLog.organization_id == user.organization_id]
    if action:
        conditions.append(AuditLog.action == action.value)
    if date_from:
        conditions.append(AuditLog.created_at >= _start_of_day(date_from))
    if date_to:
        # Up to, but not including, the start of the next day (UTC)
        conditions.append(
            AuditLog.created_at < _start_of_day(date_to + timedelta(days=1))
        )

    total = (
        db.scalar(select(func.count()).select_from(AuditLog).where(*conditions)) or 0
    )

    rows = db.execute(
        select(AuditLog, User.full_name, User.email)
        .outerjoin(User, User.id == AuditLog.actor_user_id)
        .where(*conditions)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [
        AuditLogItem(
            id=entry.id,
            action=entry.action,
            actor_user_id=entry.actor_user_id,
            actor_name=full_name or email,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            metadata=entry.event_metadata,
            created_at=entry.created_at,
        )
        for entry, full_name, email in rows
    ]

    return AuditLogPage(items=items, total=total, page=page, page_size=page_size)