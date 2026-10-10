from types import SimpleNamespace
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.permissions import (
    MANAGER_ROLES,
    STAFF_ROLES,
    ensure_same_org,
    require_role,
)
from models import User
from models.user import UserRole

StaffUser = Annotated[User, Depends(require_role(*STAFF_ROLES))]
ManagerUser = Annotated[User, Depends(require_role(*MANAGER_ROLES))]
CurrentUser = Annotated[User, Depends(get_current_user)]

app = FastAPI()


@app.get("/staff-only")
def staff_only(user: StaffUser):
    return {"role": user.role.value}


@app.get("/managers-only")
def managers_only(user: ManagerUser):
    return {"role": user.role.value}


@app.get("/org/{org_id}")
def org_resource(org_id: int, user: CurrentUser):
    ensure_same_org(user, org_id)
    return {"ok": True}


client = TestClient(app)


def login_as(role: UserRole, organization_id: int = 1) -> None:
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1, role=role, organization_id=organization_id
    )


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.parametrize("role", [UserRole.agent, UserRole.admin, UserRole.owner])
def test_staff_roles_allowed(role):
    login_as(role)
    assert client.get("/staff-only").status_code == 200


def test_customer_blocked_from_staff_route():
    login_as(UserRole.customer)
    assert client.get("/staff-only").status_code == 403


@pytest.mark.parametrize("role", [UserRole.admin, UserRole.owner])
def test_managers_allowed(role):
    login_as(role)
    assert client.get("/managers-only").status_code == 200


@pytest.mark.parametrize("role", [UserRole.customer, UserRole.agent])
def test_non_managers_blocked(role):
    login_as(role)
    assert client.get("/managers-only").status_code == 403


def test_same_org_allowed():
    login_as(UserRole.agent, organization_id=1)
    assert client.get("/org/1").status_code == 200


def test_other_org_gets_404():
    login_as(UserRole.agent, organization_id=1)
    assert client.get("/org/2").status_code == 404