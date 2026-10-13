from sqlalchemy import select

from models.audit_log import AuditLog
from models.user import UserRole

ACTION = "settings.sla_updated"


def sla_entries(db):
    return db.scalars(select(AuditLog).where(AuditLog.action == ACTION)).all()


def test_owner_reads_default_value(client, login_as, world):
    login_as(world.owner_a)
    response = client.get("/settings/sla")
    assert response.status_code == 200
    assert response.json() == {"first_reply_hours": 4}


def test_admin_can_read_and_update(client, login_as, world, make_user, db):
    admin = make_user(world.org_a, UserRole.admin, "admin.a@a.com")
    login_as(admin)

    assert client.get("/settings/sla").status_code == 200
    response = client.put("/settings/sla", json={"first_reply_hours": 8})
    assert response.status_code == 200
    assert response.json() == {"first_reply_hours": 8}

    db.refresh(world.org_a)
    assert world.org_a.sla_first_response_hours == 8


def test_owner_update_is_saved(client, login_as, world, db):
    login_as(world.owner_a)
    response = client.put("/settings/sla", json={"first_reply_hours": 24})
    assert response.status_code == 200

    db.refresh(world.org_a)
    assert world.org_a.sla_first_response_hours == 24
    assert client.get("/settings/sla").json() == {"first_reply_hours": 24}


def test_agent_and_customer_get_403(client, login_as, world):
    for user in (world.agent_a, world.customer_a):
        login_as(user)
        assert client.get("/settings/sla").status_code == 403
        assert client.put("/settings/sla", json={"first_reply_hours": 8}).status_code == 403


def test_agent_cannot_change_the_value(client, login_as, world, db):
    login_as(world.agent_a)
    client.put("/settings/sla", json={"first_reply_hours": 99})
    db.refresh(world.org_a)
    assert world.org_a.sla_first_response_hours == 4


def test_no_token_gets_401(client):
    assert client.get("/settings/sla").status_code == 401
    assert client.put("/settings/sla", json={"first_reply_hours": 8}).status_code == 401


def test_limits_are_1_to_168(client, login_as, world):
    login_as(world.owner_a)
    assert client.put("/settings/sla", json={"first_reply_hours": 1}).status_code == 200
    assert client.put("/settings/sla", json={"first_reply_hours": 168}).status_code == 200
    assert client.put("/settings/sla", json={"first_reply_hours": 0}).status_code == 422
    assert client.put("/settings/sla", json={"first_reply_hours": 169}).status_code == 422
    assert client.put("/settings/sla", json={"first_reply_hours": -5}).status_code == 422


def test_missing_or_wrong_type_gets_422(client, login_as, world):
    login_as(world.owner_a)
    assert client.put("/settings/sla", json={}).status_code == 422
    assert client.put("/settings/sla", json={"first_reply_hours": "soon"}).status_code == 422


def test_company_comes_from_the_user_not_the_request(client, login_as, world, db):
    login_as(world.owner_a)
    response = client.put(
        "/settings/sla",
        json={"first_reply_hours": 12, "organization_id": world.org_b.id},
    )
    assert response.status_code == 200

    db.refresh(world.org_a)
    db.refresh(world.org_b)
    assert world.org_a.sla_first_response_hours == 12
    assert world.org_b.sla_first_response_hours == 4


def test_each_company_has_its_own_value(client, login_as, world, make_user, db):
    owner_b = make_user(world.org_b, UserRole.owner, "owner.b@b.com")

    login_as(world.owner_a)
    client.put("/settings/sla", json={"first_reply_hours": 10})

    login_as(owner_b)
    assert client.get("/settings/sla").json() == {"first_reply_hours": 4}


def test_update_writes_an_audit_entry(client, login_as, world, db):
    login_as(world.owner_a)
    client.put("/settings/sla", json={"first_reply_hours": 24})

    entries = sla_entries(db)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.organization_id == world.org_a.id
    assert entry.actor_user_id == world.owner_a.id
    assert entry.entity_type == "organization"
    assert entry.entity_id == world.org_a.id
    assert entry.event_metadata == {"first_reply_hours": [4, 24]}


def test_same_value_writes_no_audit_entry(client, login_as, world, db):
    login_as(world.owner_a)
    response = client.put("/settings/sla", json={"first_reply_hours": 4})
    assert response.status_code == 200
    assert sla_entries(db) == []


def test_failed_requests_write_no_audit_entry(client, login_as, world, db):
    login_as(world.agent_a)
    client.put("/settings/sla", json={"first_reply_hours": 8})
    login_as(world.owner_a)
    client.put("/settings/sla", json={"first_reply_hours": 500})
    assert sla_entries(db) == []