import pytest
from sqlalchemy import select

from models import Tag
from models.user import UserRole


def all_tags(db, org_id):
    return db.scalars(select(Tag).where(Tag.organization_id == org_id)).all()


def test_agent_can_create_tag(client, world, login_as):
    login_as(world.agent_a)
    response = client.post(
        "/tags",
        json={"name": "urgent", "color": "red"},
    )
    assert response.status_code == 201
    assert response.json()["name"] == "urgent"
    assert response.json()["color"] == "red"


def test_customer_cannot_create_tag(client, world, login_as):
    login_as(world.customer_a)
    response = client.post(
        "/tags",
        json={"name": "urgent", "color": "red"},
    )
    assert response.status_code == 403


def test_list_tags_org_scoped(client, world, login_as, db):
    login_as(world.agent_a)
    client.post("/tags", json={"name": "bug", "color": "red"})
    
    login_as(world.agent_b)
    client.post("/tags", json={"name": "feature", "color": "blue"})
    
    login_as(world.agent_a)
    response = client.get("/tags")
    assert response.status_code == 200
    tags = response.json()
    assert len(tags) == 1
    assert tags[0]["name"] == "bug"
    assert tags[0]["organization_id"] == world.org_a.id


def test_agent_can_delete_tag(client, world, login_as):
    login_as(world.agent_a)
    create_response = client.post("/tags", json={"name": "test", "color": "green"})
    tag_id = create_response.json()["id"]
    delete_response = client.delete(f"/tags/{tag_id}")
    assert delete_response.status_code == 204


def test_customer_cannot_delete_tag(client, world, login_as):
    login_as(world.agent_a)
    create_response = client.post("/tags", json={"name": "test", "color": "green"})
    tag_id = create_response.json()["id"]
    login_as(world.customer_a)
    response = client.delete(f"/tags/{tag_id}")
    assert response.status_code == 403


def test_agent_can_add_tag_to_ticket(client, world, login_as):
    login_as(world.agent_a)
    tag_response = client.post("/tags", json={"name": "bug", "color": "red"})
    tag_id = tag_response.json()["id"]
    response = client.post(f"/tags/{tag_id}/tickets/{world.ticket_a.id}")
    assert response.status_code == 204


def test_customer_cannot_add_tag_to_ticket(client, world, login_as):
    login_as(world.agent_a)
    tag_response = client.post("/tags", json={"name": "bug", "color": "red"})
    tag_id = tag_response.json()["id"]
    login_as(world.customer_a)
    response = client.post(f"/tags/{tag_id}/tickets/{world.ticket_a.id}")
    assert response.status_code == 403


def test_agent_can_remove_tag_from_ticket(client, world, login_as):
    login_as(world.agent_a)
    tag_response = client.post("/tags", json={"name": "bug", "color": "red"})
    tag_id = tag_response.json()["id"]
    client.post(f"/tags/{tag_id}/tickets/{world.ticket_a.id}")
    response = client.delete(f"/tags/{tag_id}/tickets/{world.ticket_a.id}")
    assert response.status_code == 204


def test_cannot_add_same_tag_twice(client, world, login_as):
    login_as(world.agent_a)
    tag_response = client.post("/tags", json={"name": "bug", "color": "red"})
    tag_id = tag_response.json()["id"]
    client.post(f"/tags/{tag_id}/tickets/{world.ticket_a.id}")
    response = client.post(f"/tags/{tag_id}/tickets/{world.ticket_a.id}")
    assert response.status_code == 204