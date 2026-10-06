from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from core.auth import get_current_user
from database import DbSession
from models import Ticket, User
from models.user import UserRole
from schemas.ticket import (
    Priority,
    TicketCreate,
    TicketListResponse,
    TicketRead,
    TicketStatus,
    TicketUpdate,
)

router = APIRouter(prefix="/tickets", tags=["tickets"])

CurrentUser = Annotated[User, Depends(get_current_user)]


# Allowed status transitions: current status -> statuses it can move to
TRANSITIONS: dict[str, set[str]] = {
    "new": {"open"},
    "open": {"pending", "resolved"},
    "pending": {"open", "resolved"},
    "resolved": {"closed", "open"},
    "closed": {"open"},
}


def check_status_change(user: User, current: str, new: str) -> None:
    if new == current:
        return
    if new not in TRANSITIONS.get(current, set()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot change status from '{current}' to '{new}'",
        )
    if user.role == UserRole.customer and not (current == "resolved" and new == "open"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customers can only reopen resolved tickets",
        )


def visible_tickets(user: User) -> Select:
    query = select(Ticket).where(Ticket.organization_id == user.organization_id)
    if user.role == UserRole.customer:
        query = query.where(Ticket.requester_id == user.id)
    return query


def get_ticket_or_404(db: Session, user: User, ticket_id: int) -> Ticket:
    ticket = db.scalar(visible_tickets(user).where(Ticket.id == ticket_id))
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


def check_assignee(db: Session, user: User, assignee_id: int) -> None:
    assignee = db.get(User, assignee_id)
    if assignee is None or assignee.organization_id != user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assignee must be a user in your organization",
        )
    if assignee.role == UserRole.customer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tickets can only be assigned to staff",
        )
    if not assignee.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot assign tickets to an inactive user",
        )


@router.post("", response_model=TicketRead, status_code=status.HTTP_201_CREATED)
def create_ticket(payload: TicketCreate, db: DbSession, user: CurrentUser):
    ticket = Ticket(
        **payload.model_dump(),
        organization_id=user.organization_id,
        requester_id=user.id,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.get("", response_model=TicketListResponse)
def list_tickets(
    db: DbSession,
    user: CurrentUser,
    status_filter: Annotated[TicketStatus | None, Query(alias="status")] = None,
    priority: Priority | None = None,
    assignee_id: int | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    query = visible_tickets(user)

    if status_filter is not None:
        query = query.where(Ticket.status == status_filter)
    if priority is not None:
        query = query.where(Ticket.priority == priority)
    if assignee_id is not None:
        query = query.where(Ticket.assignee_id == assignee_id)

    total = db.scalar(select(func.count()).select_from(query.subquery()))

    items = db.scalars(
        query.order_by(Ticket.created_at.desc(), Ticket.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return TicketListResponse(items=items, total=total, page=page, page_size=page_size)

@router.get("/{ticket_id}", response_model=TicketRead)
def get_ticket(ticket_id: int, db: DbSession, user: CurrentUser):
    return get_ticket_or_404(db, user, ticket_id)


@router.patch("/{ticket_id}", response_model=TicketRead)
def update_ticket(ticket_id: int, payload: TicketUpdate, db: DbSession, user: CurrentUser):
    ticket = get_ticket_or_404(db, user, ticket_id)
    changes = payload.model_dump(exclude_unset=True)

    if "assignee_id" in changes:
        if user.role == UserRole.customer:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Customers cannot assign tickets",
            )
        if changes["assignee_id"] is not None:
            check_assignee(db, user, changes["assignee_id"])

    if "status" in changes:
        check_status_change(user, ticket.status, changes["status"])

    for field, value in changes.items():
        setattr(ticket, field, value)
    db.commit()
    db.refresh(ticket)
    return ticket