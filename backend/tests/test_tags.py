from sqlalchemy import select

from models import Tag


def all_tags(db, org_id):
    return db.scalars(select(Tag).where(Tag.organization_id == org_id)).all()


def test_agent_can_create_tag(client, world, login_as):
    login_as(world.agent_a)
    response = client.post(
        "/tags",
        json={"name": "urgent", "color": "#ff0000"},
    )
    assert response.status_code == 201
    assert response.json()["name"] == "urgent"
    assert response.json()["color"] == "#ff0000"


def test_customer_cannot_create_tag(client, world, login_as):
    login_as(world.customer_a)
    response = client.post(
        "/tags",
        json={"name": "urgent", "color": "#ff0000"},
    )
    assert response.status_code == 403


def test_list_tags_org_scoped(client, world, login_as, db):
    login_as(world.agent_a)
    client.post("/tags", json={"name": "bug", "color": "#ff0000"})
    
    login_as(world.agent_b)
    client.post("/tags", json={"name": "feature", "color": "#0000ff"})
    
    login_as(world.agent_a)
    response = client.get("/tags")
    assert response.status_code == 200
    tags = response.json()
    assert len(tags) == 1
    assert tags[0]["name"] == "bug"
    assert tags[0]["organization_id"] == world.org_a.id


def test_agent_can_delete_tag(client, world, login_as):
    login_as(world.agent_a)
    create_response = client.post("/tags", json={"name": "test", "color": "#00ff00"})
    tag_id = create_response.json()["id"]
    delete_response = client.delete(f"/tags/{tag_id}")
    assert delete_response.status_code == 204


def test_customer_cannot_delete_tag(client, world, login_as):
    login_as(world.agent_a)
    create_response = client.post("/tags", json={"name": "test", "color": "#00ff00"})
    tag_id = create_response.json()["id"]
    login_as(world.customer_a)
    response = client.delete(f"/tags/{tag_id}")
    assert response.status_code == 403


def test_agent_can_add_tag_to_ticket(client, world, login_as):
    login_as(world.agent_a)
    tag_response = client.post("/tags", json={"name": "bug", "color": "#ff0000"})
    tag_id = tag_response.json()["id"]
    response = client.post(f"/tags/{tag_id}/tickets/{world.ticket_a.id}")
    assert response.status_code == 204


def test_customer_cannot_add_tag_to_ticket(client, world, login_as):
    login_as(world.agent_a)
    tag_response = client.post("/tags", json={"name": "bug", "color": "#ff0000"})
    tag_id = tag_response.json()["id"]
    login_as(world.customer_a)
    response = client.post(f"/tags/{tag_id}/tickets/{world.ticket_a.id}")
    assert response.status_code == 403


def test_agent_can_remove_tag_from_ticket(client, world, login_as):
    login_as(world.agent_a)
    tag_response = client.post("/tags", json={"name": "bug", "color": "#ff0000"})
    tag_id = tag_response.json()["id"]
    client.post(f"/tags/{tag_id}/tickets/{world.ticket_a.id}")
    response = client.delete(f"/tags/{tag_id}/tickets/{world.ticket_a.id}")
    assert response.status_code == 204


def test_cannot_add_same_tag_twice(client, world, login_as):
    login_as(world.agent_a)
    tag_response = client.post("/tags", json={"name": "bug", "color": "#ff0000"})
    tag_id = tag_response.json()["id"]
    client.post(f"/tags/{tag_id}/tickets/{world.ticket_a.id}")
    response = client.post(f"/tags/{tag_id}/tickets/{world.ticket_a.id}")
    assert response.status_code == 204




def test_duplicate_tag_name_same_org_rejected(client, world, login_as):
    login_as(world.agent_a)
    client.post("/tags", json={"name": "Billing", "color": "#ff0000"})
    response = client.post("/tags", json={"name": "billing", "color": "#0000ff"})
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_same_tag_name_different_org_allowed(client, world, login_as):
    login_as(world.agent_a)
    response_a = client.post("/tags", json={"name": "billing", "color": "#ff0000"})
    assert response_a.status_code == 201

    login_as(world.agent_b)
    response_b = client.post("/tags", json={"name": "billing", "color": "#0000ff"})
    assert response_b.status_code == 201
