import logging
import os
from datetime import UTC, datetime

from sqlalchemy import Interval, literal_column, select
from sqlalchemy.orm import Session

from core.audit import AuditAction, log_audit_event
from core.email import EmailSendError, send_email
from models import Organization, Ticket, User
from models.user import UserRole

logger = logging.getLogger(__name__)

# A ticket in one of these statuses no longer needs a first reply.
FINISHED_STATUSES = ("resolved", "closed")

ALERT_ROLES = (UserRole.owner, UserRole.admin)


def _find_breached(db: Session, now: datetime):
    """Tickets with no first reply, not finished, not flagged yet, and past the SLA.

    The deadline is created_at + the company's own SLA hours.
    FOR UPDATE SKIP LOCKED: if two runs overlap, each ticket is taken by one run only.
    """
    one_hour = literal_column("interval '1 hour'", type_=Interval())
    deadline = Ticket.created_at + Organization.sla_first_response_hours * one_hour

    stmt = (
        select(Ticket, Organization.sla_first_response_hours)
        .join(Organization, Organization.id == Ticket.organization_id)
        .where(
            Ticket.first_response_at.is_(None),
            Ticket.sla_breached_at.is_(None),
            Ticket.status.notin_(FINISHED_STATUSES),
            deadline <= now,
        )
        .order_by(Ticket.id)
        .with_for_update(of=Ticket, skip_locked=True)
    )
    return db.execute(stmt).all()


def _alert_recipients(db: Session, organization_id: int) -> list[str]:
    """Emails of the active owners and admins of one company."""
    stmt = (
        select(User.email)
        .where(
            User.organization_id == organization_id,
            User.is_active.is_(True),
            User.role.in_(ALERT_ROLES),
        )
        .order_by(User.id)
    )
    return list(db.scalars(stmt))


def _build_email(alert: dict) -> tuple[str, str]:
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    created = alert["created_at"].astimezone(UTC).strftime("%Y-%m-%d %H:%M")
    # Only the ticket number goes in the subject: a ticket subject with a
    # line break would break the email header.
    subject = f"SLA breached: ticket #{alert['ticket_id']}"
    body = (
        f"Ticket #{alert['ticket_id']} has had no reply within the SLA "
        f"of {alert['hours']} hour(s).\n\n"
        f"Subject: {alert['subject']}\n"
        f"Created: {created} UTC\n"
        f"Open it: {frontend_url}/tickets/{alert['ticket_id']}\n"
    )
    return subject, body


def run_sla_check(db: Session, now: datetime) -> int:
    """Flag tickets whose first reply is overdue and email the company managers.

    Returns the number of tickets flagged in this run.

    Order: flag + audit + commit first, then send emails. If sending fails, the
    ticket stays flagged and no other email is stopped. An alert that failed is
    not retried, but the audit log still shows the breach.
    """
    rows = _find_breached(db, now)
    if not rows:
        return 0

    alerts = []
    for ticket, hours in rows:
        ticket.sla_breached_at = now
        log_audit_event(
            db,
            organization_id=ticket.organization_id,
            actor_user_id=None,  # the system did it
            action=AuditAction.ticket_sla_breached,
            entity_type="ticket",
            entity_id=ticket.id,
            metadata={"first_reply_hours": hours},
        )
        # Copy plain values now: the objects expire after the commit.
        alerts.append(
            {
                "ticket_id": ticket.id,
                "organization_id": ticket.organization_id,
                "subject": ticket.subject,
                "created_at": ticket.created_at,
                "hours": hours,
            }
        )
    db.commit()  # saves the flags and releases the row locks

    recipients_by_org: dict[int, list[str]] = {}
    for alert in alerts:
        org_id = alert["organization_id"]
        if org_id not in recipients_by_org:
            recipients_by_org[org_id] = _alert_recipients(db, org_id)
        recipients = recipients_by_org[org_id]

        if not recipients:
            logger.warning(
                "Ticket %s breached its SLA but company %s has no active owner or admin",
                alert["ticket_id"],
                org_id,
            )
            continue

        subject, body = _build_email(alert)
        for email in recipients:
            try:
                send_email(email, subject, body)
            except EmailSendError:
                logger.error(
                    "SLA alert for ticket %s could not be sent to user of company %s",
                    alert["ticket_id"],
                    org_id,
                )

    return len(alerts)