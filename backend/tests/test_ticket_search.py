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
def test_percent_literal_in_term_is_escaped(client, world, login_as):
    login_as(world.agent_a)
    client.post("/tickets", json={"subject": "100% wrong item", "description": "defective"})
    client.post("/tickets", json={"subject": "Other ticket", "description": "unrelated"})

    response = client.get("/tickets?search=100%25")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["subject"] == "100% wrong item"


def test_bare_percent_does_not_match_everything(client, world, login_as):
    login_as(world.agent_a)
    client.post("/tickets", json={"subject": "Alpha", "description": "first"})
    client.post("/tickets", json={"subject": "Beta", "description": "second"})

    response = client.get("/tickets?search=%25")
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_bare_underscore_does_not_match_everything(client, world, login_as):
    login_as(world.agent_a)
    client.post("/tickets", json={"subject": "Alpha", "description": "first"})

    response = client.get("/tickets?search=_")
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_underscore_matches_literal_underscore_only(client, world, login_as):
    login_as(world.agent_a)
    client.post("/tickets", json={"subject": "Login_problem", "description": "cannot sign in"})
    client.post("/tickets", json={"subject": "LoginXproblem", "description": "should not match"})

    response = client.get("/tickets?search=Login_p")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["subject"] == "Login_problem"


def test_sql_injection_attempt_is_safe(client, world, login_as):
    login_as(world.agent_a)
    client.post("/tickets", json={"subject": "Normal ticket", "description": "fine"})

    response = client.get("/tickets?search=' OR 1=1 --")
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_search_requires_auth(client, world):
    response = client.get("/tickets?search=order")
    assert response.status_code == 401


def test_search_with_invalid_status_still_422(client, world, login_as):
    login_as(world.agent_a)
    response = client.get("/tickets?search=order&status=banana")
    assert response.status_code == 422


def test_empty_search_is_rejected(client, world, login_as):
    login_as(world.agent_a)
    response = client.get("/tickets?search=")
    assert response.status_code == 422


def test_search_too_long_is_rejected(client, world, login_as):
    login_as(world.agent_a)
    response = client.get("/tickets?search=" + "a" * 256)
    assert response.status_code == 422


def test_unmatched_search_returns_empty_not_error(client, world, login_as):
    login_as(world.agent_a)
    response = client.get("/tickets?search=zzzzzznomatch")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_total_counts_all_matches_not_just_current_page(client, world, login_as):
    login_as(world.agent_a)
    client.post("/tickets", json={"subject": "Order one", "description": "x"})
    client.post("/tickets", json={"subject": "Order two", "description": "y"})

    response = client.get("/tickets?search=order&page=1&page_size=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["total"] == 2