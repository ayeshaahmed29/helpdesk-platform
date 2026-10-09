from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from models import User
from models.user import UserRole

from core.auth import get_current_user

STAFF_ROLES = (UserRole.agent, UserRole.admin, UserRole.owner)
MANAGER_ROLES = (UserRole.admin, UserRole.owner)


def require_role(*allowed_roles: UserRole) -> Callable[..., User]:
    """Dependency that only lets the given roles through.

    Usage: current_user: User = Depends(require_role(UserRole.admin, UserRole.owner))
    Returns the current user, or raises 403 if the role is not allowed.
    A missing or invalid token is already a 401 from get_current_user.
    """

    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to do this",
            )
        return user

    return dependency


def ensure_same_org(user: User, resource_org_id: int) -> None:
    """Raise 404 if a record belongs to another organization.

    404 (not 403) so one company cannot learn that another company's record exists.
    """
    if user.organization_id != resource_org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )