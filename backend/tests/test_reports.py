from datetime import UTC, datetime, timedelta

import pytest

from models.user import UserRole


@pytest.fixture
def company(db, make_org, make_user):
    org = make_org("FastMart")
    return {
        "org": org,
        "owner": make_user(org, UserRole.owner, "owner@fastmart.com"),
        "agent": make_user(org, UserRole.agent, "agent@fastmart.com"),
        "customer": make_user(org, UserRole.customer, "customer@fastmart.com"),
    }


@pytest.fixture
def dated_ticket(db, make_ticket):
    """dated_ticket(org, requester, created_at, first_response_at=None) makes a ticket
    with explicit timestamps, bypassing the API so we control dates exactly."""

    def _dated_ticket(org, requester, created_at, first_response_at=None, subject="Ticket"):
        ticket = make_ticket(org, requester, subject)
        ticket.created_at = created_at
        ticket.first_response_at = first_response_at
        db.commit()
        db.refresh(ticket)
        return ticket

    return _dated_ticket


# ---- Permissions ----


def test_customer_blocked_from_tickets_per_day(client, company, login_as):
    login_as(company["customer"])
    response = client.get("/reports/tickets-per-day")
    assert response.status_code == 403


def test_customer_blocked_from_avg_first_response(client, company, login_as):
    login_as(company["customer"])
    response = client.get("/reports/avg-first-response")
    assert response.status_code == 403


def test_agent_can_access_tickets_per_day(client, company, login_as):
    login_as(company["agent"])
    response = client.get("/reports/tickets-per-day")
    assert response.status_code == 200


def test_agent_can_access_avg_first_response(client, company, login_as):
    login_as(company["agent"])
    response = client.get("/reports/avg-first-response")
    assert response.status_code == 200


def test_no_token_gets_401(client, company):
    response = client.get("/reports/tickets-per-day")
    assert response.status_code == 401

    response = client.get("/reports/avg-first-response")
    assert response.status_code == 401


# ---- tickets-per-day correctness ----


def test_tickets_per_day_groups_by_day(client, company, dated_ticket, login_as):
    login_as(company["owner"])
    day1 = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    day2 = datetime(2026, 10, 2, 14, 0, tzinfo=UTC)

    dated_ticket(company["org"], company["customer"], day1)
    dated_ticket(company["org"], company["customer"], day1 + timedelta(hours=2))
    dated_ticket(company["org"], company["customer"], day2)

    response = client.get("/reports/tickets-per-day")
    assert response.status_code == 200
    items = {item["day"]: item["count"] for item in response.json()["items"]}
    assert items["2026-10-01"] == 2
    assert items["2026-10-02"] == 1


def test_tickets_per_day_respects_date_range(client, company, dated_ticket, login_as):
    login_as(company["owner"])
    dated_ticket(company["org"], company["customer"], datetime(2026, 10, 1, tzinfo=UTC))
    dated_ticket(company["org"], company["customer"], datetime(2026, 10, 5, tzinfo=UTC))
    dated_ticket(company["org"], company["customer"], datetime(2026, 10, 10, tzinfo=UTC))

    response = client.get(
        "/reports/tickets-per-day?date_from=2026-10-03&date_to=2026-10-07"
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["day"] == "2026-10-05"


def test_tickets_per_day_date_to_is_inclusive(client, company, dated_ticket, login_as):
    login_as(company["owner"])
    dated_ticket(
        company["org"], company["customer"], datetime(2026, 10, 5, 23, 59, tzinfo=UTC)
    )

    response = client.get("/reports/tickets-per-day?date_to=2026-10-05")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["day"] == "2026-10-05"


def test_tickets_per_day_date_from_after_date_to_returns_400(client, company, login_as):
    login_as(company["owner"])
    response = client.get(
        "/reports/tickets-per-day?date_from=2026-10-10&date_to=2026-10-01"
    )
    assert response.status_code == 400


def test_tickets_per_day_empty_result_when_no_tickets(client, company, login_as):
    login_as(company["owner"])
    response = client.get("/reports/tickets-per-day?date_from=2099-01-01")
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_tickets_per_day_other_org_not_counted(
    client, company, make_org, make_user, dated_ticket, login_as
):
    other_org = make_org("QuickBank")
    other_customer = make_user(other_org, UserRole.customer, "customer@quickbank.com")
    same_day = datetime(2026, 10, 1, tzinfo=UTC)

    dated_ticket(company["org"], company["customer"], same_day)
    dated_ticket(other_org, other_customer, same_day)

    login_as(company["owner"])
    response = client.get("/reports/tickets-per-day")
    items = {item["day"]: item["count"] for item in response.json()["items"]}
    assert items["2026-10-01"] == 1


def test_tickets_per_day_only_date_from_is_open_ended(
    client, company, dated_ticket, login_as
):
    login_as(company["owner"])
    dated_ticket(company["org"], company["customer"], datetime(2026, 10, 1, tzinfo=UTC))
    dated_ticket(company["org"], company["customer"], datetime(2099, 1, 1, tzinfo=UTC))

    response = client.get("/reports/tickets-per-day?date_from=2026-10-01")
    assert response.status_code == 200
    assert len(response.json()["items"]) == 2


def test_tickets_per_day_counts_regardless_of_status(
    client, company, dated_ticket, login_as, db
):
    login_as(company["owner"])
    day = datetime(2026, 10, 1, tzinfo=UTC)
    t1 = dated_ticket(company["org"], company["customer"], day)
    t2 = dated_ticket(company["org"], company["customer"], day)
    t1.status = "resolved"
    t2.status = "closed"
    db.commit()

    response = client.get("/reports/tickets-per-day")
    items = {item["day"]: item["count"] for item in response.json()["items"]}
    assert items["2026-10-01"] == 2


def test_tickets_per_day_invalid_date_format_returns_422(client, company, login_as):
    login_as(company["owner"])
    response = client.get("/reports/tickets-per-day?date_from=not-a-date")
    assert response.status_code == 422


# ---- avg-first-response correctness ----


def test_avg_first_response_calculates_correctly(client, company, dated_ticket, login_as):
    login_as(company["owner"])
    created = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    dated_ticket(
        company["org"], company["customer"], created, created + timedelta(hours=2)
    )
    dated_ticket(
        company["org"], company["customer"], created, created + timedelta(hours=4)
    )

    response = client.get("/reports/avg-first-response")
    assert response.status_code == 200
    data = response.json()
    assert data["average_hours"] == 3.0
    assert data["ticket_count"] == 2


def test_avg_first_response_excludes_tickets_with_no_reply(
    client, company, dated_ticket, login_as
):
    login_as(company["owner"])
    created = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    dated_ticket(
        company["org"], company["customer"], created, created + timedelta(hours=2)
    )
    dated_ticket(company["org"], company["customer"], created, None)

    response = client.get("/reports/avg-first-response")
    data = response.json()
    assert data["average_hours"] == 2.0
    assert data["ticket_count"] == 1


def test_avg_first_response_no_data_returns_none(client, company, login_as):
    login_as(company["owner"])
    response = client.get("/reports/avg-first-response")
    assert response.status_code == 200
    data = response.json()
    assert data["average_hours"] is None
    assert data["ticket_count"] == 0


def test_avg_first_response_respects_date_range(client, company, dated_ticket, login_as):
    login_as(company["owner"])
    in_range = datetime(2026, 10, 5, tzinfo=UTC)
    out_of_range = datetime(2026, 10, 20, tzinfo=UTC)

    dated_ticket(
        company["org"], company["customer"], in_range, in_range + timedelta(hours=1)
    )
    dated_ticket(
        company["org"], company["customer"], out_of_range, out_of_range + timedelta(hours=10)
    )

    response = client.get(
        "/reports/avg-first-response?date_from=2026-10-01&date_to=2026-10-10"
    )
    data = response.json()
    assert data["ticket_count"] == 1
    assert data["average_hours"] == 1.0


def test_avg_first_response_date_from_after_date_to_returns_400(client, company, login_as):
    login_as(company["owner"])
    response = client.get(
        "/reports/avg-first-response?date_from=2026-10-10&date_to=2026-10-01"
    )
    assert response.status_code == 400


def test_avg_first_response_other_org_not_counted(
    client, company, make_org, make_user, dated_ticket, login_as
):
    other_org = make_org("QuickBank")
    other_customer = make_user(other_org, UserRole.customer, "customer@quickbank.com")
    created = datetime(2026, 10, 1, tzinfo=UTC)

    dated_ticket(
        company["org"], company["customer"], created, created + timedelta(hours=1)
    )
    dated_ticket(other_org, other_customer, created, created + timedelta(hours=100))

    login_as(company["owner"])
    response = client.get("/reports/avg-first-response")
    data = response.json()
    assert data["ticket_count"] == 1
    assert data["average_hours"] == 1.0


def test_avg_first_response_invalid_date_format_returns_422(client, company, login_as):
    login_as(company["owner"])
    response = client.get("/reports/avg-first-response?date_to=not-a-date")
    assert response.status_code == 422