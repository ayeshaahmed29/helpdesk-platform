from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from models.user import UserRole


class UserAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str | None
    role: UserRole
    is_active: bool
    organization_id: int
    created_at: datetime


class UserUpdate(BaseModel):
    # unknown fields (for example a typo like "active") return 422
    model_config = ConfigDict(extra="forbid")

    role: UserRole | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> Self:
        if self.role is None and self.is_active is None:
            raise ValueError("Send at least one of: role, is_active")
        return self