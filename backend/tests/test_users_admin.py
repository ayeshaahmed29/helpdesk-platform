from sqlalchemy import select

from models.audit_log import AuditLog
from models.user import UserRole


def entries(db, action):
    return db.scalars(select(AuditLog).where(AuditLog.action == action)).all()


# ---------- GET /users ----------


def test_owner_lists_only_own_company_users(client, login_as, world):
    login_as(world.owner_a)
    response = client.get("/users")
    assert response.status_code == 200

    emails = {item["email"] for item in response.json()}
    assert emails == {
        "owner.a@a.com",
        "agent.a@a.com",
        "customer.a@a.com",
        "customer.a2@a.com",
    }
    assert "agent.b@b.com" not in emails


def test_list_does_not_return_password_hashes(client, login_as, world):
    login_as(world.owner_a)
    items = client.get("/users").json()
    assert all("hashed_password" not in item for item in items)
    assert all({"id", "email", "role", "is_active"} <= set(item) for item in items)


def test_admin_can_list(client, login_as, world, make_user):
    admin = make_user(world.org_a, UserRole.admin, "admin.a@a.com")
    login_as(admin)
    assert client.get("/users").status_code == 200


def test_agent_and_customer_cannot_list(client, login_as, world):
    for user in (world.agent_a, world.customer_a):
        login_as(user)
        assert client.get("/users").status_code == 403


def test_list_without_token_gets_401(client):
    assert client.get("/users").status_code == 401


# ---------- PATCH /users/{id}: roles and permissions ----------


def test_owner_changes_role_and_it_is_audited(client, login_as, world, db):
    login_as(world.owner_a)
    response = client.patch(f"/users/{world.agent_a.id}", json={"role": "admin"})
    assert response.status_code == 200
    assert response.json()["role"] == "admin"

    db.refresh(world.agent_a)
    assert world.agent_a.role == UserRole.admin

    logged = entries(db, "user.role_changed")
    assert len(logged) == 1
    assert logged[0].organization_id == world.org_a.id
    assert logged[0].actor_user_id == world.owner_a.id
    assert logged[0].entity_type == "user"
    assert logged[0].entity_id == world.agent_a.id
    assert logged[0].event_metadata == {"role": ["agent", "admin"]}


def test_audit_metadata_has_no_personal_data(client, login_as, world, db):
    login_as(world.owner_a)
    client.patch(f"/users/{world.agent_a.id}", json={"role": "admin"})
    client.patch(f"/users/{world.customer_a.id}", json={"is_active": False})

    for entry in db.scalars(select(AuditLog)).all():
        text = str(entry.event_metadata)
        assert "@" not in text
        assert "agent.a" not in text


def test_admin_can_change_an_agent(client, login_as, world, make_user, db):
    admin = make_user(world.org_a, UserRole.admin, "admin.a@a.com")
    login_as(admin)
    response = client.patch(f"/users/{world.agent_a.id}", json={"role": "customer"})
    assert response.status_code == 200
    db.refresh(world.agent_a)
    assert world.agent_a.role == UserRole.customer


def test_owner_can_make_someone_an_owner(client, login_as, world, db):
    login_as(world.owner_a)
    response = client.patch(f"/users/{world.agent_a.id}", json={"role": "owner"})
    assert response.status_code == 200
    db.refresh(world.agent_a)
    assert world.agent_a.role == UserRole.owner


def test_admin_cannot_make_an_owner(client, login_as, world, make_user, db):
    admin = make_user(world.org_a, UserRole.admin, "admin.a@a.com")
    login_as(admin)
    response = client.patch(f"/users/{world.agent_a.id}", json={"role": "owner"})
    assert response.status_code == 403
    db.refresh(world.agent_a)
    assert world.agent_a.role == UserRole.agent
    assert entries(db, "user.role_changed") == []


def test_admin_cannot_change_or_deactivate_an_owner(client, login_as, world, make_user, db):
    admin = make_user(world.org_a, UserRole.admin, "admin.a@a.com")
    login_as(admin)

    for body in ({"role": "agent"}, {"is_active": False}, {"role": "admin"}):
        response = client.patch(f"/users/{world.owner_a.id}", json=body)
        assert response.status_code == 403

    db.refresh(world.owner_a)
    assert world.owner_a.role == UserRole.owner
    assert world.owner_a.is_active is True


def test_agent_and_customer_cannot_patch(client, login_as, world, db):
    for user in (world.agent_a, world.customer_a):
        login_as(user)
        response = client.patch(f"/users/{world.customer_a2.id}", json={"role": "agent"})
        assert response.status_code == 403
    db.refresh(world.customer_a2)
    assert world.customer_a2.role == UserRole.customer


# ---------- PATCH /users/{id}: deactivate ----------


def test_deactivate_user_and_audit(client, login_as, world, db):
    login_as(world.owner_a)
    response = client.patch(f"/users/{world.agent_a.id}", json={"is_active": False})
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    db.refresh(world.agent_a)
    assert world.agent_a.is_active is False

    logged = entries(db, "user.deactivated")
    assert len(logged) == 1
    assert logged[0].entity_id == world.agent_a.id
    assert logged[0].event_metadata == {"is_active": [True, False]}


def test_reactivate_user(client, login_as, world, db):
    world.agent_a.is_active = False
    db.commit()

    login_as(world.owner_a)
    response = client.patch(f"/users/{world.agent_a.id}", json={"is_active": True})
    assert response.status_code == 200
    db.refresh(world.agent_a)
    assert world.agent_a.is_active is True


def test_role_and_deactivate_in_one_request_write_two_entries(client, login_as, world, db):
    login_as(world.owner_a)
    response = client.patch(
        f"/users/{world.agent_a.id}", json={"role": "customer", "is_active": False}
    )
    assert response.status_code == 200
    assert len(entries(db, "user.role_changed")) == 1
    assert len(entries(db, "user.deactivated")) == 1


def test_no_change_writes_no_audit_entry(client, login_as, world, db):
    login_as(world.owner_a)
    response = client.patch(
        f"/users/{world.agent_a.id}", json={"role": "agent", "is_active": True}
    )
    assert response.status_code == 200
    assert db.scalars(select(AuditLog)).all() == []


# ---------- PATCH /users/{id}: self rules ----------


def test_nobody_can_demote_themselves(client, login_as, world, make_user, db):
    other_owner = make_user(world.org_a, UserRole.owner, "owner2.a@a.com")
    admin = make_user(world.org_a, UserRole.admin, "admin.a@a.com")

    login_as(other_owner)
    assert client.patch(f"/users/{other_owner.id}", json={"role": "agent"}).status_code == 403

    login_as(admin)
    assert client.patch(f"/users/{admin.id}", json={"role": "agent"}).status_code == 403

    db.refresh(other_owner)
    db.refresh(admin)
    assert other_owner.role == UserRole.owner
    assert admin.role == UserRole.admin


def test_nobody_can_deactivate_themselves(client, login_as, world, make_user, db):
    admin = make_user(world.org_a, UserRole.admin, "admin.a@a.com")

    login_as(world.owner_a)
    assert client.patch(f"/users/{world.owner_a.id}", json={"is_active": False}).status_code == 403

    login_as(admin)
    assert client.patch(f"/users/{admin.id}", json={"is_active": False}).status_code == 403

    db.refresh(world.owner_a)
    db.refresh(admin)
    assert world.owner_a.is_active is True
    assert admin.is_active is True


def test_sending_your_own_current_role_is_allowed(client, login_as, world):
    login_as(world.owner_a)
    response = client.patch(f"/users/{world.owner_a.id}", json={"role": "owner"})
    assert response.status_code == 200


# ---------- PATCH /users/{id}: last active owner ----------


def test_owner_can_demote_another_owner_when_an_active_owner_remains(
    client, login_as, world, make_user, db
):
    second_owner = make_user(world.org_a, UserRole.owner, "owner2.a@a.com")
    login_as(world.owner_a)

    response = client.patch(f"/users/{second_owner.id}", json={"role": "admin"})
    assert response.status_code == 200
    db.refresh(second_owner)
    assert second_owner.role == UserRole.admin


def test_last_active_owner_cannot_be_demoted_or_deactivated(
    client, login_as, world, make_user, db
):
    # The acting owner is inactive in the database (the test login skips that
    # check), so the target is the only active owner left in the company.
    last_owner = make_user(world.org_a, UserRole.owner, "owner2.a@a.com")
    world.owner_a.is_active = False
    db.commit()
    login_as(world.owner_a)

    for body in ({"role": "agent"}, {"is_active": False}):
        response = client.patch(f"/users/{last_owner.id}", json=body)
        assert response.status_code == 409

    db.refresh(last_owner)
    assert last_owner.role == UserRole.owner
    assert last_owner.is_active is True
    assert entries(db, "user.role_changed") == []
    assert entries(db, "user.deactivated") == []


# ---------- PATCH /users/{id}: other company and bad input ----------


def test_user_from_another_company_returns_404(client, login_as, world, db):
    login_as(world.owner_a)

    for body in ({"role": "admin"}, {"is_active": False}):
        response = client.patch(f"/users/{world.agent_b.id}", json=body)
        assert response.status_code == 404

    db.refresh(world.agent_b)
    assert world.agent_b.role == UserRole.agent
    assert world.agent_b.is_active is True
    assert db.scalars(select(AuditLog)).all() == []


def test_missing_user_and_other_company_look_the_same(client, login_as, world):
    login_as(world.owner_a)
    missing = client.patch("/users/99999", json={"role": "admin"})
    other_company = client.patch(f"/users/{world.agent_b.id}", json={"role": "admin"})
    assert missing.status_code == other_company.status_code == 404
    assert missing.json() == other_company.json()


def test_bad_input_gets_422(client, login_as, world):
    login_as(world.owner_a)
    url = f"/users/{world.agent_a.id}"
    assert client.patch(url, json={}).status_code == 422
    assert client.patch(url, json={"role": "superuser"}).status_code == 422
    assert client.patch(url, json={"active": False}).status_code == 422
    assert client.patch(url, json={"organization_id": 2, "role": "admin"}).status_code == 422