from datetime import datetime

from models.user import UserRole
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class InviteCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    role: UserRole


class InviteOut(BaseModel):
    id: int
    email: str
    role: str
    status: str  # "pending", "accepted" or "expired"
    invited_by: int | None
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime


class InvitePreview(BaseModel):
    """What the accept-invite page shows before the person sets a password."""

    email: str
    role: str
    organization_name: str
    expires_at: datetime


class AcceptInviteRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)