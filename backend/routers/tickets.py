from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from core.auth import get_current_user
from database import DbSession
from models import Ticket, User
from models.user import UserRole
from schemas.ticket import TicketCreate, TicketRead, TicketUpdate

router = APIRouter(prefix="/tickets", tags=["tickets"])

CurrentUser = Annotated[User, Depends(get_current_user)]


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


@router.get("", response_model=list[TicketRead])
def list_tickets(db: DbSession, user: CurrentUser):
    query = visible_tickets(user).order_by(Ticket.created_at.desc())
    return db.scalars(query).all()


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

    for field, value in changes.items():
        setattr(ticket, field, value)
    db.commit()
    db.refresh(ticket)
    return ticket