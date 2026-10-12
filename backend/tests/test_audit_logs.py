from datetime import datetime, timezone

import pytest

from core.audit import AuditAction, log_audit_event
from models.user import UserRole


def add_entry(
    db, org, action=AuditAction.ticket_created, actor=None, created_at=None
):
    entry = log_audit_event(
        db,
        organization_id=org.id,
        actor_user_id=actor.id if actor else None,
        action=action,
        entity_type="ticket",
        entity_id=1,
    )
    if created_at is not None:
        entry.created_at = created_at
    db.commit()
    return entry


def day(number, hour=12, minute=0):
    return datetime(2026, 10, number, hour, minute, tzinfo=timezone.utc)


def ids(response):
    return [item["id"] for item in response.json()["items"]]


def test_other_orgs_logs_never_appear(client, db, login_as, make_user, world):
    a1 = add_entry(db, world.org_a)
    b1 = add_entry(db, world.org_b)
    b2 = add_entry(db, world.org_b)
    admin_b = make_user(world.org_b, UserRole.admin, "admin.b@b.com")

    login_as(world.owner_a)
    response = client.get("/audit-logs")
    assert response.status_code == 200
    assert ids(response) == [a1.id]
    assert response.json()["total"] == 1

    # Filters must not let another company's entries through either
    response = client.get("/audit-logs?action=ticket.created&date_from=2026-01-01")
    assert ids(response) == [a1.id]

    login_as(admin_b)
    response = client.get("/audit-logs")
    assert ids(response) == [b2.id, b1.id]
    assert response.json()["total"] == 2


def test_admin_can_view(client, db, login_as, make_user, world):
    entry = add_entry(db, world.org_a)
    admin_a = make_user(world.org_a, UserRole.admin, "admin.a@a.com")

    login_as(admin_a)
    response = client.get("/audit-logs")

    assert response.status_code == 200
    assert ids(response) == [entry.id]


def test_agent_and_customer_are_forbidden(client, db, login_as, world):
    add_entry(db, world.org_a)

    login_as(world.agent_a)
    assert client.get("/audit-logs").status_code == 403

    login_as(world.customer_a)
    assert client.get("/audit-logs").status_code == 403


def test_filter_by_action(client, db, login_as, world):
    created = add_entry(db, world.org_a, AuditAction.ticket_created)
    add_entry(db, world.org_a, AuditAction.invite_created)

    login_as(world.owner_a)
    response = client.get("/audit-logs?action=ticket.created")

    assert response.status_code == 200
    assert ids(response) == [created.id]
    assert response.json()["total"] == 1


def test_unknown_action_returns_422(client, login_as, world):
    login_as(world.owner_a)

    assert client.get("/audit-logs?action=ticket.craeted").status_code == 422


def test_filter_by_date_range(client, db, login_as, world):
    e1 = add_entry(db, world.org_a, created_at=day(1))
    e2 = add_entry(db, world.org_a, created_at=day(5, hour=23, minute=30))
    e3 = add_entry(db, world.org_a, created_at=day(10, hour=9))

    login_as(world.owner_a)

    response = client.get("/audit-logs?date_from=2026-10-05")
    assert ids(response) == [e3.id, e2.id]

    # date_to includes the whole day, so 23:30 on the 5th is still inside
    response = client.get("/audit-logs?date_to=2026-10-05")
    assert ids(response) == [e2.id, e1.id]

    response = client.get("/audit-logs?date_from=2026-10-05&date_to=2026-10-05")
    assert ids(response) == [e2.id]


def test_date_from_after_date_to_returns_400(client, login_as, world):
    login_as(world.owner_a)

    response = client.get("/audit-logs?date_from=2026-10-10&date_to=2026-10-01")

    assert response.status_code == 400


def test_pagination_newest_first(client, db, login_as, world):
    entries = [add_entry(db, world.org_a, created_at=day(n)) for n in range(1, 6)]
    newest_first = [entry.id for entry in reversed(entries)]

    login_as(world.owner_a)

    response = client.get("/audit-logs?page=1&page_size=2")
    body = response.json()
    assert ids(response) == newest_first[0:2]
    assert body["total"] == 5
    assert body["page"] == 1
    assert body["page_size"] == 2

    response = client.get("/audit-logs?page=3&page_size=2")
    assert ids(response) == newest_first[4:5]

    response = client.get("/audit-logs?page=4&page_size=2")
    assert ids(response) == []
    assert response.json()["total"] == 5


@pytest.mark.parametrize("query", ["page=0", "page_size=0", "page_size=101"])
def test_invalid_pagination_returns_422(client, login_as, world, query):
    login_as(world.owner_a)

    assert client.get(f"/audit-logs?{query}").status_code == 422


def test_item_has_actor_name_or_none_for_system(client, db, login_as, world):
    by_agent = add_entry(db, world.org_a, actor=world.agent_a, created_at=day(2))
    by_system = add_entry(db, world.org_a, created_at=day(1))

    login_as(world.owner_a)
    items = client.get("/audit-logs").json()["items"]

    assert items[0]["id"] == by_agent.id
    assert items[0]["actor_user_id"] == world.agent_a.id
    assert items[0]["actor_name"] == "agent.a"
    assert items[0]["action"] == "ticket.created"
    assert items[0]["entity_type"] == "ticket"
    assert items[0]["entity_id"] == 1
    assert items[1]["id"] == by_system.id
    assert items[1]["actor_user_id"] is None
    assert items[1]["actor_name"] is None