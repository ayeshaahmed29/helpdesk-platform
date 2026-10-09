from enum import StrEnum
from typing import Any

from models.audit_log import AuditLog
from sqlalchemy.orm import Session


class AuditAction(StrEnum):
    """Every allowed audit action name. Format: <entity>.<what happened>."""

    # accounts
    user_signup = "user.signup"
    user_login = "user.login"
    user_password_reset_requested = "user.password_reset_requested"
    user_password_reset = "user.password_reset"

    # invites
    invite_created = "invite.created"
    invite_accepted = "invite.accepted"

    # tickets (called from Saqeeba's endpoints)
    ticket_created = "ticket.created"
    ticket_updated = "ticket.updated"
    ticket_status_changed = "ticket.status_changed"


def log_audit_event(
    db: Session,
    *,
    organization_id: int,
    action: AuditAction | str,
    actor_user_id: int | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    """Add one audit entry to the current session.

    It does NOT commit. The caller's commit saves the audit entry together with
    the real change, so you never get one without the other.
    An unknown action name raises ValueError (this catches typos).
    """
    entry = AuditLog(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=AuditAction(action).value,
        entity_type=entity_type,
        entity_id=entity_id,
        event_metadata=metadata or {},
    )
    db.add(entry)
    return entry