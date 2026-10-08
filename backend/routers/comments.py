from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from core.auth import get_current_user
from database import DbSession
from models import Comment, User
from models.user import UserRole
from routers.tickets import get_ticket_or_404
from schemas.comment import CommentCreate, CommentRead

router = APIRouter(prefix="/tickets/{ticket_id}/comments", tags=["comments"])

CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
def create_comment(
    ticket_id: int,
    payload: CommentCreate,
    db: DbSession,
    user: CurrentUser,
):
    ticket = get_ticket_or_404(db, user, ticket_id)

    if payload.is_internal and user.role == UserRole.customer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customers cannot post internal notes",
        )

    comment = Comment(
        ticket_id=ticket.id,
        author_id=user.id,
        body=payload.body,
        is_internal=payload.is_internal,
    )
    db.add(comment)

    # First public staff reply sets first_response_at
    if (
        user.role != UserRole.customer
        and not payload.is_internal
        and ticket.first_response_at is None
    ):
        ticket.first_response_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(comment)
    return comment


@router.get("", response_model=list[CommentRead])
def list_comments(
    ticket_id: int,
    db: DbSession,
    user: CurrentUser,
):
    ticket = get_ticket_or_404(db, user, ticket_id)

    query = select(Comment).where(Comment.ticket_id == ticket.id)

    # Customers never see internal notes
    if user.role == UserRole.customer:
        query = query.where(Comment.is_internal.is_(False))

    comments = db.scalars(query.order_by(Comment.created_at)).all()
    return list(comments)