from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


class TagCreate(BaseModel):
    name: Name
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class TagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str | None
    organization_id: int
    created_at: datetime