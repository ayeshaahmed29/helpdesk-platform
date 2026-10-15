from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from core.permissions import STAFF_ROLES, require_role
from database import DbSession
from models import Ticket, User
from schemas.reports import (
    AvgFirstResponseResponse,
    TicketsPerDayItem,
    TicketsPerDayResponse,
)

router = APIRouter(prefix="/reports", tags=["reports"])

StaffUser = Annotated[User, Depends(require_role(*STAFF_ROLES))]


def _start_of_day(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


@router.get("/tickets-per-day", response_model=TicketsPerDayResponse)
def tickets_per_day(
    user: StaffUser,
    db: DbSession,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=400, detail="date_from must not be after date_to"
        )

    conditions = [Ticket.organization_id == user.organization_id]
    if date_from:
        conditions.append(Ticket.created_at >= _start_of_day(date_from))
    if date_to:
        conditions.append(
            Ticket.created_at < _start_of_day(date_to + timedelta(days=1))
        )

    day_column = func.date(Ticket.created_at).label("day")
    rows = db.execute(
        select(day_column, func.count().label("count"))
        .where(*conditions)
        .group_by(day_column)
        .order_by(day_column)
    ).all()

    items = [TicketsPerDayItem(day=row.day, count=row.count) for row in rows]
    return TicketsPerDayResponse(items=items)


@router.get("/avg-first-response", response_model=AvgFirstResponseResponse)
def avg_first_response(
    user: StaffUser,
    db: DbSession,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=400, detail="date_from must not be after date_to"
        )

    conditions = [
        Ticket.organization_id == user.organization_id,
        Ticket.first_response_at.is_not(None),
    ]
    if date_from:
        conditions.append(Ticket.created_at >= _start_of_day(date_from))
    if date_to:
        conditions.append(
            Ticket.created_at < _start_of_day(date_to + timedelta(days=1))
        )

    rows = db.execute(
        select(Ticket.created_at, Ticket.first_response_at).where(*conditions)
    ).all()

    if not rows:
        return AvgFirstResponseResponse(average_hours=None, ticket_count=0)

    total_hours = sum(
        (first_response_at - created_at).total_seconds() / 3600
        for created_at, first_response_at in rows
    )
    average_hours = round(total_hours / len(rows), 2)

    return AvgFirstResponseResponse(average_hours=average_hours, ticket_count=len(rows))