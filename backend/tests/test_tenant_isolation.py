import pytest


def ids(response):
    return {item["id"] for item in response.json()["items"]}


# --- Company A cannot see or change company B's data ---


def test_agent_sees_only_own_org_tickets(client, login_as, world):
    login_as(world.agent_a)
    response = client.get("/tickets")
    assert response.status_code == 200
    assert ids(response) == {world.ticket_a.id, world.ticket_a2.id}
    assert response.json()["total"] == 2


def test_other_org_agent_sees_only_their_tickets(client, login_as, world):
    login_as(world.agent_b)
    response = client.get("/tickets")
    assert response.status_code == 200
    assert ids(response) == {world.ticket_b.id}


def test_agent_cannot_read_other_org_ticket(client, login_as, world):
    login_as(world.agent_a)
    response = client.get(f"/tickets/{world.ticket_b.id}")
    assert response.status_code == 404


def test_agent_cannot_update_other_org_ticket(client, login_as, db, world):
    login_as(world.agent_a)
    response = client.patch(f"/tickets/{world.ticket_b.id}", json={"subject": "Hacked"})
    assert response.status_code == 404
    db.refresh(world.ticket_b)
    assert world.ticket_b.subject == "Org B ticket"


# --- Customers only see their own tickets ---


def test_customer_sees_only_own_tickets(client, login_as, world):
    login_as(world.customer_a)
    response = client.get("/tickets")
    assert response.status_code == 200
    assert ids(response) == {world.ticket_a.id}


def test_customer_cannot_read_another_customers_ticket(client, login_as, world):
    login_as(world.customer_a)
    response = client.get(f"/tickets/{world.ticket_a2.id}")
    assert response.status_code == 404


# --- Assigning tickets ---


def test_customer_cannot_assign_tickets(client, login_as, world):
    login_as(world.customer_a)
    response = client.patch(
        f"/tickets/{world.ticket_a.id}", json={"assignee_id": world.agent_a.id}
    )
    assert response.status_code == 403


def test_agent_can_assign_to_staff_in_same_org(client, login_as, world):
    login_as(world.agent_a)
    response = client.patch(
        f"/tickets/{world.ticket_a.id}", json={"assignee_id": world.owner_a.id}
    )
    assert response.status_code == 200
    assert response.json()["assignee_id"] == world.owner_a.id


def test_agent_cannot_assign_to_other_org_user(client, login_as, world):
    login_as(world.agent_a)
    response = client.patch(
        f"/tickets/{world.ticket_a.id}", json={"assignee_id": world.agent_b.id}
    )
    assert response.status_code == 400


def test_agent_cannot_assign_to_customer(client, login_as, world):
    login_as(world.agent_a)
    response = client.patch(
        f"/tickets/{world.ticket_a.id}", json={"assignee_id": world.customer_a.id}
    )
    assert response.status_code == 400


# --- Creating tickets ---


def test_created_ticket_ignores_org_in_payload(client, login_as, world):
    login_as(world.agent_a)
    response = client.post(
        "/tickets",
        json={
            "subject": "Hello",
            "description": "Trying to write into another company",
            "organization_id": world.org_b.id,
            "requester_id": world.customer_b.id,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["organization_id"] == world.org_a.id
    assert body["requester_id"] == world.agent_a.id


# --- Login is required ---


@pytest.mark.parametrize("path", ["/tickets", "/auth/me"])
def test_requires_login(client, path):
    response = client.get(path)
    assert response.status_code == 401