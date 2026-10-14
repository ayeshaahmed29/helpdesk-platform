def test_search_matches_subject(client, world, login_as):
    login_as(world.agent_a)
    client.post("/tickets", json={"subject": "Printer is broken", "description": "won't turn on"})
    client.post("/tickets", json={"subject": "Invoice question", "description": "need a copy"})

    response = client.get("/tickets?search=printer")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["subject"] == "Printer is broken"


def test_search_matches_description(client, world, login_as):
    login_as(world.agent_a)
    client.post("/tickets", json={"subject": "Order issue", "description": "the package arrived late"})

    response = client.get("/tickets?search=arrived late")
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_search_is_case_insensitive(client, world, login_as):
    login_as(world.agent_a)
    client.post("/tickets", json={"subject": "URGENT Server Down", "description": "help"})

    response = client.get("/tickets?search=urgent")
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_search_combines_with_status_filter(client, world, login_as):
    login_as(world.agent_a)
    client.post("/tickets", json={"subject": "Login problem", "description": "cannot sign in"})

    response = client.get("/tickets?search=login&status=new")
    assert response.status_code == 200
    assert response.json()["total"] == 1

    response = client.get("/tickets?search=login&status=resolved")
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_search_other_org_not_matched(client, world, login_as):
    login_as(world.agent_a)
    client.post("/tickets", json={"subject": "Shared keyword ticket", "description": "test"})

    login_as(world.agent_b)
    response = client.get("/tickets?search=shared keyword")
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_no_search_returns_all(client, world, login_as):
    login_as(world.agent_a)
    response = client.get("/tickets")
    assert response.status_code == 200