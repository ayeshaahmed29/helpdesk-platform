from datetime import datetime

from database import Base
from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column


class Invite(Base):
    __tablename__ = "invites"
    __table_args__ = (
        Index("ix_invites_organization_id_email", "organization_id", "email"),
        Index("ix_invites_token_hash", "token_hash", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    # Stored as the lowercase role value (customer, agent, admin, owner)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", name="fk_invites_organization_id"),
        nullable=False,
    )
    invited_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_invites_invited_by", ondelete="SET NULL"),
        nullable=True,
    )
    # SHA-256 hex of the token. The real token is only in the email link.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )