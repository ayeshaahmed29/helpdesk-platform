from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from core.email import EmailSendError
from core.sla import run_sla_check
from models import AuditLog
from models.user import UserRole

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


@pytest.fixture
def sent_emails(monkeypatch):
    """Replace send_email where core.sla uses it, and collect what would be sent."""
    sent = []

    def fake_send_email(to, subject, body):
        sent.append({"to": to, "subject": subject, "body": body})

    monkeypatch.setattr("core.sla.send_email", fake_send_email)
    return sent


@pytest.fixture
def company(db, make_org, make_user):
    org = make_org("FastMart")
    org.sla_first_response_hours = 4
    db.commit()
    return SimpleNamespace(
        org=org,
        owner=make_user(org, UserRole.owner, "owner@fastmart.com"),
        admin=make_user(org, UserRole.admin, "admin@fastmart.com"),
        agent=make_user(org, UserRole.agent, "agent@fastmart.com"),
        customer=make_user(org, UserRole.customer, "customer@fastmart.com"),
    )


@pytest.fixture
def old_ticket(db, make_ticket):
    """old_ticket(org, requester, hours_old) makes a ticket created hours_old before NOW."""

    def _old_ticket(org, requester, hours_old, subject="Late order"):
        ticket = make_ticket(org, requester, subject)
        ticket.created_at = NOW - timedelta(hours=hours_old)
        db.commit()
        return ticket

    return _old_ticket


def test_breached_ticket_is_flagged_and_emailed(db, company, old_ticket, sent_emails):
    ticket = old_ticket(company.org, company.customer, hours_old=5)

    flagged = run_sla_check(db, NOW)

    assert flagged == 1
    db.refresh(ticket)
    assert ticket.sla_breached_at == NOW
    # Only the owner and the admin get the email, not the agent or the customer.
    assert {m["to"] for m in sent_emails} == {"owner@fastmart.com", "admin@fastmart.com"}
    assert all(f"#{ticket.id}" in m["subject"] for m in sent_emails)


def test_breach_writes_an_audit_entry_without_actor(db, company, old_ticket, sent_emails):
    ticket = old_ticket(company.org, company.customer, hours_old=5)

    run_sla_check(db, NOW)

    entries = db.scalars(
        select(AuditLog).where(AuditLog.action == "ticket.sla_breached")
    ).all()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.actor_user_id is None
    assert entry.organization_id == company.org.id
    assert entry.entity_type == "ticket"
    assert entry.entity_id == ticket.id
    assert entry.event_metadata == {"first_reply_hours": 4}


def test_ticket_with_first_response_is_ignored(db, company, old_ticket, sent_emails):
    ticket = old_ticket(company.org, company.customer, hours_old=5)
    ticket.first_response_at = NOW - timedelta(hours=3)
    db.commit()

    assert run_sla_check(db, NOW) == 0

    db.refresh(ticket)
    assert ticket.sla_breached_at is None
    assert sent_emails == []


@pytest.mark.parametrize("status", ["resolved", "closed"])
def test_finished_ticket_is_ignored(db, company, old_ticket, sent_emails, status):
    ticket = old_ticket(company.org, company.customer, hours_old=5)
    ticket.status = status
    db.commit()

    assert run_sla_check(db, NOW) == 0

    db.refresh(ticket)
    assert ticket.sla_breached_at is None
    assert sent_emails == []


def test_ticket_still_inside_the_sla_is_ignored(db, company, old_ticket, sent_emails):
    ticket = old_ticket(company.org, company.customer, hours_old=3)  # SLA is 4 hours

    assert run_sla_check(db, NOW) == 0

    db.refresh(ticket)
    assert ticket.sla_breached_at is None
    assert sent_emails == []


def test_second_run_does_not_email_again(db, company, old_ticket, sent_emails):
    old_ticket(company.org, company.customer, hours_old=5)

    assert run_sla_check(db, NOW) == 1
    assert len(sent_emails) == 2  # owner + admin

    assert run_sla_check(db, NOW + timedelta(hours=1)) == 0
    assert len(sent_emails) == 2  # no new emails

    entries = db.scalars(
        select(AuditLog).where(AuditLog.action == "ticket.sla_breached")
    ).all()
    assert len(entries) == 1  # no second audit entry


def test_each_company_uses_its_own_sla_hours(
    db, make_org, make_user, old_ticket, sent_emails
):
    fast = make_org("Fast Co")
    fast.sla_first_response_hours = 2
    slow = make_org("Slow Co")
    slow.sla_first_response_hours = 8
    db.commit()

    make_user(fast, UserRole.owner, "owner@fast.com")
    fast_customer = make_user(fast, UserRole.customer, "customer@fast.com")
    make_user(slow, UserRole.owner, "owner@slow.com")
    slow_customer = make_user(slow, UserRole.customer, "customer@slow.com")

    # Both tickets are 3 hours old: late for Fast Co (2h), fine for Slow Co (8h).
    fast_ticket = old_ticket(fast, fast_customer, hours_old=3)
    slow_ticket = old_ticket(slow, slow_customer, hours_old=3)

    assert run_sla_check(db, NOW) == 1

    db.refresh(fast_ticket)
    db.refresh(slow_ticket)
    assert fast_ticket.sla_breached_at is not None
    assert slow_ticket.sla_breached_at is None
    # The other company's owner never gets an email about this ticket.
    assert [m["to"] for m in sent_emails] == ["owner@fast.com"]


def test_inactive_admin_is_not_emailed(db, company, old_ticket, sent_emails):
    company.admin.is_active = False
    db.commit()
    old_ticket(company.org, company.customer, hours_old=5)

    run_sla_check(db, NOW)

    assert [m["to"] for m in sent_emails] == ["owner@fastmart.com"]


def test_email_failure_does_not_stop_the_run(db, company, old_ticket, monkeypatch):
    calls = []

    def flaky_send_email(to, subject, body):
        calls.append(to)
        if len(calls) == 1:
            raise EmailSendError("SMTP is down")

    monkeypatch.setattr("core.sla.send_email", flaky_send_email)
    first = old_ticket(company.org, company.customer, hours_old=5, subject="First")
    second = old_ticket(company.org, company.customer, hours_old=6, subject="Second")

    flagged = run_sla_check(db, NOW)

    assert flagged == 2
    assert len(calls) == 4  # 2 tickets x (owner + admin), the failed one did not stop the rest
    db.refresh(first)
    db.refresh(second)
    assert first.sla_breached_at is not None
    assert second.sla_breached_at is not None