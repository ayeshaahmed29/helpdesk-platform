import pytest
from sqlalchemy import select

from core.audit import AuditAction, log_audit_event
from models import AuditLog
from models.user import UserRole

SIGNUP = {
    "organization_name": "FastMart",
    "full_name": "Owner One",
    "email": "owner@fastmart.com",
    "password": "correct-horse-battery",
}


def all_entries(db):
    return db.scalars(select(AuditLog).order_by(AuditLog.id)).all()


def test_log_audit_event_saves_all_fields(db, make_org, make_user):
    org = make_org("Org A")
    agent = make_user(org, UserRole.agent, "agent@a.com")

    log_audit_event(
        db,
        organization_id=org.id,
        actor_user_id=agent.id,
        action=AuditAction.ticket_status_changed,
        entity_type="ticket",
        entity_id=7,
        metadata={"status": ["new", "open"]},
    )
    db.commit()

    entry = all_entries(db)[0]
    assert entry.organization_id == org.id
    assert entry.actor_user_id == agent.id
    assert entry.action == "ticket.status_changed"
    assert entry.entity_type == "ticket"
    assert entry.entity_id == 7
    assert entry.event_metadata == {"status": ["new", "open"]}
    assert entry.created_at is not None


def test_actor_entity_and_metadata_are_optional(db, make_org):
    org = make_org("Org A")

    log_audit_event(db, organization_id=org.id, action=AuditAction.ticket_created)
    db.commit()

    entry = all_entries(db)[0]
    assert entry.actor_user_id is None
    assert entry.entity_type is None
    assert entry.entity_id is None
    assert entry.event_metadata == {}


def test_plain_string_action_is_accepted(db, make_org):
    org = make_org("Org A")

    log_audit_event(db, organization_id=org.id, action="ticket.created")
    db.commit()

    assert all_entries(db)[0].action == "ticket.created"


def test_unknown_action_is_rejected(db, make_org):
    org = make_org("Org A")

    with pytest.raises(ValueError):
        log_audit_event(db, organization_id=org.id, action="ticket.craeted")


def test_helper_does_not_commit(db, make_org):
    org = make_org("Org A")

    log_audit_event(db, organization_id=org.id, action=AuditAction.ticket_created)
    db.rollback()

    assert all_entries(db) == []


def test_signup_writes_audit_entry(client, db):
    response = client.post("/auth/signup", json=SIGNUP)
    assert response.status_code == 201
    body = response.json()

    entries = all_entries(db)
    assert len(entries) == 1
    assert entries[0].action == "user.signup"
    assert entries[0].organization_id == body["organization_id"]
    assert entries[0].actor_user_id == body["id"]
    assert entries[0].entity_type == "user"
    assert entries[0].entity_id == body["id"]
    assert entries[0].event_metadata == {"role": "owner"}


def test_duplicate_signup_writes_no_audit_entry(client, db):
    client.post("/auth/signup", json=SIGNUP)
    response = client.post("/auth/signup", json=SIGNUP)

    assert response.status_code == 409
    assert len(all_entries(db)) == 1


def test_login_writes_audit_entry(client, db):
    user_id = client.post("/auth/signup", json=SIGNUP).json()["id"]

    response = client.post(
        "/auth/login",
        json={"email": SIGNUP["email"], "password": SIGNUP["password"]},
    )
    assert response.status_code == 200

    entries = all_entries(db)
    assert [entry.action for entry in entries] == ["user.signup", "user.login"]
    assert entries[1].actor_user_id == user_id
    assert entries[1].entity_id == user_id


def test_failed_login_writes_no_audit_entry(client, db):
    client.post("/auth/signup", json=SIGNUP)

    wrong_password = client.post(
        "/auth/login", json={"email": SIGNUP["email"], "password": "wrong-password"}
    )
    unknown_email = client.post(
        "/auth/login", json={"email": "nobody@fastmart.com", "password": "whatever-123"}
    )

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert [entry.action for entry in all_entries(db)] == ["user.signup"]