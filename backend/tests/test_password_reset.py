import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import pytest
from models import AuditLog, PasswordResetToken
from security import hash_password, verify_password
from sqlalchemy import select

OLD_PASSWORD = "the-old-password"
NEW_PASSWORD = "the-new-password"


@pytest.fixture
def sent_emails(monkeypatch):
    """Replaces send_email, so tests never send anything. Collects what would be sent."""
    sent = []

    def fake_send_email(to, subject, body):
        sent.append({"to": to, "subject": subject, "body": body})

    monkeypatch.setattr("routers.auth.send_email", fake_send_email)
    return sent


@pytest.fixture
def member(world, db):
    """An agent with a real password hash, so we can check old and new passwords."""
    user = world.agent_a
    user.hashed_password = hash_password(OLD_PASSWORD)
    db.commit()
    return user


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def token_from_email(email):
    return email["body"].split("/reset-password/")[1].split()[0]


def make_reset_token(db, user, expires_in=timedelta(hours=1), used=False):
    """Creates a reset token directly in the database. Returns (row, token)."""
    token = secrets.token_urlsafe(32)
    row = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=datetime.now(timezone.utc) + expires_in,
        used_at=datetime.now(timezone.utc) if used else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, token


def forgot(client, email):
    return client.post("/auth/forgot-password", json={"email": email})


def reset(client, token, password=NEW_PASSWORD):
    return client.post(
        "/auth/reset-password", json={"token": token, "new_password": password}
    )


def login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


# ---------- asking for a reset link ----------


def test_known_email_gets_a_link_and_an_audit_entry(client, member, sent_emails, db):
    response = forgot(client, member.email)

    assert response.status_code == 202
    assert len(sent_emails) == 1
    assert sent_emails[0]["to"] == member.email
    assert "/reset-password/" in sent_emails[0]["body"]

    entries = db.scalars(
        select(AuditLog).where(AuditLog.action == "user.password_reset_requested")
    ).all()
    assert len(entries) == 1
    assert entries[0].organization_id == member.organization_id
    assert entries[0].actor_user_id == member.id
    assert entries[0].entity_type == "user"
    assert entries[0].entity_id == member.id
    assert token_from_email(sent_emails[0]) not in str(entries[0].event_metadata)


def test_only_the_token_hash_is_stored(client, member, sent_emails, db):
    forgot(client, member.email)

    token = token_from_email(sent_emails[0])
    row = db.scalar(select(PasswordResetToken))

    assert row.user_id == member.id
    assert row.token_hash == hash_token(token)
    assert row.token_hash != token
    assert row.used_at is None


def test_unknown_email_gets_the_same_response_and_nothing_else(
    client, member, sent_emails, db
):
    known = forgot(client, member.email)
    unknown = forgot(client, "nobody@nowhere.com")

    assert unknown.status_code == known.status_code == 202
    assert unknown.json() == known.json()

    # only the known email produced an email, a token and an audit entry
    assert len(sent_emails) == 1
    assert len(db.scalars(select(PasswordResetToken)).all()) == 1
    assert len(db.scalars(select(AuditLog)).all()) == 1


def test_inactive_user_gets_the_same_response_and_nothing_else(
    client, member, sent_emails, db
):
    member.is_active = False
    db.commit()

    response = forgot(client, member.email)

    assert response.status_code == 202
    assert sent_emails == []
    assert db.scalars(select(PasswordResetToken)).all() == []


def test_email_is_matched_in_lowercase(client, member, sent_emails):
    response = forgot(client, member.email.upper())

    assert response.status_code == 202
    assert len(sent_emails) == 1


def test_invalid_email_format_is_rejected(client, sent_emails):
    assert forgot(client, "not-an-email").status_code == 422
    assert sent_emails == []


# ---------- resetting the password ----------


def test_reset_changes_the_password(client, member, db):
    _, token = make_reset_token(db, member)

    response = reset(client, token)

    assert response.status_code == 200
    db.refresh(member)
    assert verify_password(NEW_PASSWORD, member.hashed_password)
    assert not verify_password(OLD_PASSWORD, member.hashed_password)


def test_old_password_stops_working_and_new_one_works(client, member, db):
    _, token = make_reset_token(db, member)
    assert login(client, member.email, OLD_PASSWORD).status_code == 200

    reset(client, token)

    assert login(client, member.email, OLD_PASSWORD).status_code == 401
    assert login(client, member.email, NEW_PASSWORD).status_code == 200


def test_reset_marks_token_used_and_writes_audit_entry(client, member, db):
    row, token = make_reset_token(db, member)

    reset(client, token)

    db.refresh(row)
    assert row.used_at is not None

    entries = db.scalars(
        select(AuditLog).where(AuditLog.action == "user.password_reset")
    ).all()
    assert len(entries) == 1
    assert entries[0].organization_id == member.organization_id
    assert entries[0].actor_user_id == member.id
    assert entries[0].entity_id == member.id
    assert NEW_PASSWORD not in str(entries[0].event_metadata)
    assert token not in str(entries[0].event_metadata)


def test_reused_token_fails(client, member, db):
    _, token = make_reset_token(db, member)

    first = reset(client, token, password="first-new-password")
    second = reset(client, token, password="second-new-password")

    assert first.status_code == 200
    assert second.status_code == 410
    db.refresh(member)
    assert verify_password("first-new-password", member.hashed_password)


def test_already_used_token_fails(client, member, db):
    _, token = make_reset_token(db, member, used=True)

    assert reset(client, token).status_code == 410


def test_expired_token_fails_and_password_stays(client, member, db):
    _, token = make_reset_token(db, member, expires_in=timedelta(minutes=-1))

    response = reset(client, token)

    assert response.status_code == 410
    db.refresh(member)
    assert verify_password(OLD_PASSWORD, member.hashed_password)


def test_unknown_token_fails(client):
    assert reset(client, "not-a-real-token").status_code == 404


def test_short_password_is_rejected_and_token_stays_usable(client, member, db):
    row, token = make_reset_token(db, member)

    response = reset(client, token, password="short")

    assert response.status_code == 422
    db.refresh(row)
    assert row.used_at is None
    assert reset(client, token).status_code == 200


def test_other_reset_links_of_the_same_user_stop_working(client, member, db):
    _, first_token = make_reset_token(db, member)
    _, second_token = make_reset_token(db, member)

    assert reset(client, first_token).status_code == 200
    assert reset(client, second_token).status_code == 410


def test_inactive_user_cannot_reset(client, member, db):
    _, token = make_reset_token(db, member)
    member.is_active = False
    db.commit()

    assert reset(client, token).status_code == 410


def test_full_flow_from_email_link(client, member, sent_emails):
    forgot(client, member.email)
    token = token_from_email(sent_emails[0])

    assert reset(client, token).status_code == 200
    assert login(client, member.email, NEW_PASSWORD).status_code == 200