from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index(
            "ix_audit_logs_organization_id_created_at",
            "organization_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", name="fk_audit_logs_organization_id"),
        nullable=False,
    )
    # NULL means the system did it (for example the SLA job), or the user was deleted
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_audit_logs_actor_user_id", ondelete="SET NULL"),
        nullable=True,
    )

    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(nullable=True)

    # The column is called "metadata", but that name is reserved on SQLAlchemy models
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )