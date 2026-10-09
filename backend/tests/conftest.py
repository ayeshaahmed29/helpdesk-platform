from types import SimpleNamespace

import pytest
from core.auth import get_current_user
from database import DATABASE_URL, Base, get_db
from fastapi.testclient import TestClient
from main import app
from models import Ticket, User
from models.organization import Organization
from models.user import UserRole
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

TEST_DB_NAME = "helpdesk_test"
TEST_DATABASE_URL = make_url(DATABASE_URL).set(database=TEST_DB_NAME)


@pytest.fixture(scope="session")
def engine():
    """A separate test database, created once per test run."""
    admin_engine = create_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": TEST_DB_NAME},
        )
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    admin_engine.dispose()

    test_engine = create_engine(TEST_DATABASE_URL)
    # Safety: never run table drops or truncates on anything but the test database
    assert test_engine.url.database == TEST_DB_NAME

    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    yield test_engine
    Base.metadata.drop_all(test_engine)
    test_engine.dispose()


@pytest.fixture
def db(engine):
    """One session per test. All tables are emptied after the test."""
    session = sessionmaker(bind=engine, autoflush=False)()
    yield session
    session.close()
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def client(db):
    def override_get_db():
        return db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def login_as(client):
    """Call login_as(user) to make the next requests come from that user."""

    def _login_as(user):
        app.dependency_overrides[get_current_user] = lambda: user

    return _login_as


@pytest.fixture
def make_org(db):
    def _make_org(name):
        org = Organization(name=name)
        db.add(org)
        db.commit()
        db.refresh(org)
        return org

    return _make_org


@pytest.fixture
def make_user(db):
    def _make_user(org, role, email):
        user = User(
            email=email,
            hashed_password="not-used-in-tests",
            full_name=email.split("@")[0],
            role=role,
            organization_id=org.id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make_user


@pytest.fixture
def make_ticket(db):
    def _make_ticket(org, requester, subject):
        ticket = Ticket(
            subject=subject,
            description="Test description",
            organization_id=org.id,
            requester_id=requester.id,
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        return ticket

    return _make_ticket


@pytest.fixture
def world(make_org, make_user, make_ticket):
    """Two companies, each with staff and customers, plus some tickets."""
    org_a = make_org("Org A")
    org_b = make_org("Org B")

    customer_a = make_user(org_a, UserRole.customer, "customer.a@a.com")
    customer_a2 = make_user(org_a, UserRole.customer, "customer.a2@a.com")
    customer_b = make_user(org_b, UserRole.customer, "customer.b@b.com")

    return SimpleNamespace(
        org_a=org_a,
        org_b=org_b,
        owner_a=make_user(org_a, UserRole.owner, "owner.a@a.com"),
        agent_a=make_user(org_a, UserRole.agent, "agent.a@a.com"),
        agent_b=make_user(org_b, UserRole.agent, "agent.b@b.com"),
        customer_a=customer_a,
        customer_a2=customer_a2,
        customer_b=customer_b,
        ticket_a=make_ticket(org_a, customer_a, "Org A ticket"),
        ticket_a2=make_ticket(org_a, customer_a2, "Org A second ticket"),
        ticket_b=make_ticket(org_b, customer_b, "Org B ticket"),
    )