from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from core.auth import get_current_user
from database import DbSession
from models import Tag, Ticket, User
from models.user import UserRole
from routers.tickets import get_ticket_or_404
from schemas.tag import TagCreate, TagRead

router = APIRouter(prefix="/tags", tags=["tags"])

CurrentUser = Annotated[User, Depends(get_current_user)]


def get_tag_or_404(db: DbSession, user: User, tag_id: int) -> Tag:
    """Fetch tag and verify it belongs to user's organization."""
    tag = db.scalar(select(Tag).where(Tag.id == tag_id))
    if not tag or tag.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    return tag


@router.post("", response_model=TagRead, status_code=status.HTTP_201_CREATED)
def create_tag(
    payload: TagCreate,
    db: DbSession,
    user: CurrentUser,
):
    if user.role == UserRole.customer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customers cannot create tags",
        )

    tag = Tag(
        name=payload.name,
        color=payload.color,
        organization_id=user.organization_id,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


@router.get("", response_model=list[TagRead])
def list_tags(
    db: DbSession,
    user: CurrentUser,
):
    tags = db.scalars(
        select(Tag)
        .where(Tag.organization_id == user.organization_id)
        .order_by(Tag.created_at)
    ).all()
    return list(tags)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(
    tag_id: int,
    db: DbSession,
    user: CurrentUser,
):
    if user.role == UserRole.customer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customers cannot delete tags",
        )

    tag = get_tag_or_404(db, user, tag_id)
    db.delete(tag)
    db.commit()


@router.post("/{tag_id}/tickets/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def add_tag_to_ticket(
    tag_id: int,
    ticket_id: int,
    db: DbSession,
    user: CurrentUser,
):
    if user.role == UserRole.customer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customers cannot add tags to tickets",
        )

    tag = get_tag_or_404(db, user, tag_id)
    ticket = get_ticket_or_404(db, user, ticket_id)

    if tag not in ticket.tags:
        ticket.tags.append(tag)
        db.commit()


@router.delete("/{tag_id}/tickets/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_tag_from_ticket(
    tag_id: int,
    ticket_id: int,
    db: DbSession,
    user: CurrentUser,
):
    if user.role == UserRole.customer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customers cannot remove tags from tickets",
        )

    tag = get_tag_or_404(db, user, tag_id)
    ticket = get_ticket_or_404(db, user, ticket_id)

    if tag in ticket.tags:
        ticket.tags.remove(tag)
        db.commit()