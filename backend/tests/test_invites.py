import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from core.email import EmailSendError
from models import AuditLog, Invite, User
from models.user import UserRole
from security import verify_password

PASSWORD = "a-good-password"


@pytest.fixture
def sent_emails(monkeypatch):
    """Replaces send_email, so tests never send anything. Collects what would be sent."""
    sent = []

    def fake_send_email(to, subject, body):
        sent.append({"to": to, "subject": subject, "body": body})

    monkeypatch.setattr("routers.invites.send_email", fake_send_email)
    return sent


@pytest.fixture
def admin_a(world, make_user):
    return make_user(world.org_a, UserRole.admin, "admin.a@a.com")


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def token_from_email(email):
    return email["body"].split("/accept-invite/")[1].split()[0]


def make_invite(
    db,
    org,
    email,
    role="agent",
    invited_by=None,
    expires_in=timedelta(days=7),
    accepted=False,
):
    """Creates an invite directly in the database. Returns (invite, token)."""
    token = secrets.token_urlsafe(32)
    invite = Invite(
        email=email,
        role=role,
        organization_id=org.id,
        invited_by=invited_by.id if invited_by else None,
        token_hash=hash_token(token),
        expires_at=datetime.now(timezone.utc) + expires_in,
        accepted_at=datetime.now(timezone.utc) if accepted else None,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite, token


def accept(client, token, password=PASSWORD):
    return client.post(
        f"/invites/{token}/accept",
        json={"full_name": "New Person", "password": password},
    )


# ---------- creating invites ----------


def test_owner_can_invite_agent(client, login_as, world, sent_emails, db):
    login_as(world.owner_a)

    response = client.post("/invites", json={"email": "new.agent@a.com", "role": "agent"})

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new.agent@a.com"
    assert body["role"] == "agent"
    assert body["status"] == "pending"
    assert body["invited_by"] == world.owner_a.id
    assert "token" not in body
    assert "token_hash" not in body

    assert len(sent_emails) == 1
    assert sent_emails[0]["to"] == "new.agent@a.com"
    assert "/accept-invite/" in sent_emails[0]["body"]


def test_only_the_token_hash_is_stored(client, login_as, world, sent_emails, db):
    login_as(world.owner_a)
    client.post("/invites", json={"email": "new.agent@a.com", "role": "agent"})

    token = token_from_email(sent_emails[0])
    invite = db.scalar(select(Invite))

    assert invite.token_hash == hash_token(token)
    assert invite.token_hash != token


def test_invite_created_writes_audit_entry(client, login_as, world, sent_emails, db):
    login_as(world.owner_a)
    response = client.post("/invites", json={"email": "new.agent@a.com", "role": "agent"})

    entries = db.scalars(select(AuditLog).where(AuditLog.action == "invite.created")).all()

    assert len(entries) == 1
    entry = entries[0]
    assert entry.organization_id == world.org_a.id
    assert entry.actor_user_id == world.owner_a.id
    assert entry.entity_type == "invite"
    assert entry.entity_id == response.json()["id"]
    assert entry.event_metadata == {"role": "agent"}
    assert token_from_email(sent_emails[0]) not in str(entry.event_metadata)


def test_invite_email_is_saved_in_lowercase(client, login_as, world, sent_emails, db):
    login_as(world.owner_a)
    response = client.post("/invites", json={"email": "New.Agent@A.com", "role": "agent"})

    assert response.status_code == 201
    assert response.json()["email"] == "new.agent@a.com"


@pytest.mark.parametrize("role", ["customer", "agent", "admin"])
def test_admin_can_invite_non_owner_roles(client, login_as, admin_a, sent_emails, role):
    login_as(admin_a)

    response = client.post("/invites", json={"email": "new.person@a.com", "role": role})

    assert response.status_code == 201
    assert response.json()["role"] == role


def test_admin_cannot_invite_an_owner(client, login_as, admin_a, sent_emails, db):
    login_as(admin_a)

    response = client.post("/invites", json={"email": "new.owner@a.com", "role": "owner"})

    assert response.status_code == 403
    assert db.scalars(select(Invite)).all() == []
    assert sent_emails == []


def test_owner_can_invite_another_owner(client, login_as, world, sent_emails):
    login_as(world.owner_a)

    response = client.post("/invites", json={"email": "new.owner@a.com", "role": "owner"})

    assert response.status_code == 201
    assert response.json()["role"] == "owner"


@pytest.mark.parametrize("who", ["agent_a", "customer_a"])
def test_agent_and_customer_cannot_invite(client, login_as, world, sent_emails, db, who):
    login_as(getattr(world, who))

    response = client.post("/invites", json={"email": "new.agent@a.com", "role": "agent"})

    assert response.status_code == 403
    assert db.scalars(select(Invite)).all() == []
    assert sent_emails == []


def test_invalid_role_is_rejected(client, login_as, world, sent_emails):
    login_as(world.owner_a)

    response = client.post("/invites", json={"email": "new.agent@a.com", "role": "boss"})

    assert response.status_code == 422


def test_duplicate_pending_invite_is_blocked(client, login_as, world, sent_emails):
    login_as(world.owner_a)

    first = client.post("/invites", json={"email": "new.agent@a.com", "role": "agent"})
    second = client.post("/invites", json={"email": "new.agent@a.com", "role": "admin"})

    assert first.status_code == 201
    assert second.status_code == 409
    assert len(sent_emails) == 1


def test_expired_invite_does_not_block_a_new_one(client, login_as, world, sent_emails, db):
    make_invite(db, world.org_a, "again@a.com", expires_in=timedelta(days=-1))
    login_as(world.owner_a)

    response = client.post("/invites", json={"email": "again@a.com", "role": "agent"})

    assert response.status_code == 201


def test_pending_invite_in_another_company_does_not_block(
    client, login_as, world, sent_emails, db
):
    make_invite(db, world.org_b, "shared@x.com")
    login_as(world.owner_a)

    response = client.post("/invites", json={"email": "shared@x.com", "role": "agent"})

    assert response.status_code == 201


def test_existing_member_cannot_be_invited(client, login_as, world, sent_emails):
    login_as(world.owner_a)

    same_company = client.post("/invites", json={"email": "agent.a@a.com", "role": "agent"})
    other_company = client.post("/invites", json={"email": "agent.b@b.com", "role": "agent"})

    assert same_company.status_code == 409
    assert other_company.status_code == 409
    assert sent_emails == []


def test_failed_email_saves_nothing(client, login_as, world, db, monkeypatch):
    def broken_send_email(to, subject, body):
        raise EmailSendError("SMTP is down")

    monkeypatch.setattr("routers.invites.send_email", broken_send_email)
    login_as(world.owner_a)

    response = client.post("/invites", json={"email": "new.agent@a.com", "role": "agent"})

    assert response.status_code == 502
    assert db.scalars(select(Invite)).all() == []
    assert db.scalars(select(AuditLog)).all() == []


# ---------- listing invites ----------


def test_list_shows_only_own_company_invites(client, login_as, world, db):
    make_invite(db, world.org_a, "one@a.com")
    make_invite(db, world.org_a, "two@a.com", expires_in=timedelta(days=-1))
    make_invite(db, world.org_a, "three@a.com", accepted=True)
    make_invite(db, world.org_b, "other@b.com")
    login_as(world.owner_a)

    response = client.get("/invites")

    assert response.status_code == 200
    statuses = {item["email"]: item["status"] for item in response.json()}
    assert statuses == {"one@a.com": "pending", "two@a.com": "expired", "three@a.com": "accepted"}


def test_list_is_for_owner_and_admin_only(client, login_as, world, admin_a):
    login_as(world.agent_a)
    assert client.get("/invites").status_code == 403

    login_as(world.customer_a)
    assert client.get("/invites").status_code == 403

    login_as(admin_a)
    assert client.get("/invites").status_code == 200


# ---------- looking up an invite ----------


def test_lookup_valid_token(client, world, db):
    _, token = make_invite(db, world.org_a, "new.agent@a.com", role="agent")

    response = client.get(f"/invites/{token}")

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "new.agent@a.com"
    assert body["role"] == "agent"
    assert body["organization_name"] == "Org A"
    assert "token_hash" not in body


def test_lookup_unknown_token(client):
    assert client.get("/invites/not-a-real-token").status_code == 404


def test_lookup_expired_token(client, world, db):
    _, token = make_invite(db, world.org_a, "late@a.com", expires_in=timedelta(days=-1))

    assert client.get(f"/invites/{token}").status_code == 410


def test_lookup_used_token(client, world, db):
    _, token = make_invite(db, world.org_a, "used@a.com", accepted=True)

    assert client.get(f"/invites/{token}").status_code == 410


# ---------- accepting an invite ----------


@pytest.mark.parametrize("role", ["customer", "agent", "admin", "owner"])
def test_accept_creates_user_with_invited_role(client, world, db, role):
    _, token = make_invite(db, world.org_a, "new.person@a.com", role=role)

    response = accept(client, token)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new.person@a.com"
    assert body["role"] == role
    assert body["organization_id"] == world.org_a.id
    assert "hashed_password" not in body

    user = db.scalar(select(User).where(User.email == "new.person@a.com"))
    assert user.role == UserRole(role)
    assert user.organization_id == world.org_a.id
    assert user.is_active is True
    assert user.full_name == "New Person"
    assert verify_password(PASSWORD, user.hashed_password)


def test_accept_marks_invite_used_and_writes_audit_entry(client, world, db):
    invite, token = make_invite(db, world.org_a, "new.agent@a.com", invited_by=world.owner_a)

    response = accept(client, token)

    assert response.status_code == 201
    db.refresh(invite)
    assert invite.accepted_at is not None

    entries = db.scalars(select(AuditLog).where(AuditLog.action == "invite.accepted")).all()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.organization_id == world.org_a.id
    assert entry.actor_user_id == response.json()["id"]
    assert entry.entity_type == "invite"
    assert entry.entity_id == invite.id
    assert entry.event_metadata == {"role": "agent"}


def test_accept_in_other_company_creates_user_there(client, world, db):
    _, token = make_invite(db, world.org_b, "new.agent@b.com")

    response = accept(client, token)

    assert response.status_code == 201
    assert response.json()["organization_id"] == world.org_b.id


def test_reusing_a_token_fails(client, world, db):
    _, token = make_invite(db, world.org_a, "new.agent@a.com")

    first = accept(client, token)
    second = accept(client, token)

    assert first.status_code == 201
    assert second.status_code == 410
    users = db.scalars(select(User).where(User.email == "new.agent@a.com")).all()
    assert len(users) == 1


def test_expired_token_cannot_be_accepted(client, world, db):
    _, token = make_invite(db, world.org_a, "late@a.com", expires_in=timedelta(days=-1))

    response = accept(client, token)

    assert response.status_code == 410
    assert db.scalar(select(User).where(User.email == "late@a.com")) is None


def test_unknown_token_cannot_be_accepted(client):
    assert accept(client, "not-a-real-token").status_code == 404


def test_accept_fails_if_email_was_registered_meanwhile(client, world, db, make_user):
    invite, token = make_invite(db, world.org_a, "late@a.com")
    make_user(world.org_b, UserRole.agent, "late@a.com")

    response = accept(client, token)

    assert response.status_code == 409
    db.refresh(invite)
    assert invite.accepted_at is None


def test_short_password_is_rejected_and_invite_stays_usable(client, world, db):
    invite, token = make_invite(db, world.org_a, "new.agent@a.com")

    response = accept(client, token, password="short")

    assert response.status_code == 422
    db.refresh(invite)
    assert invite.accepted_at is None
    assert accept(client, token).status_code == 201