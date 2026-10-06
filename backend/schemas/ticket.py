from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Priority = Literal["low", "normal", "high", "urgent"]
TicketStatus = Literal["new", "open", "pending", "resolved", "closed"]

class TicketCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
   


class TicketUpdate(BaseModel):
    subject: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1)
    priority: Priority | None = None
    assignee_id: int | None = None
    status: TicketStatus | None = None


class TicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject: str
    description: str
    status: str
    priority: str
    organization_id: int
    requester_id: int
    assignee_id: int | None
    first_response_at: datetime | None
    created_at: datetime
    updated_at: datetime
class TicketListResponse(BaseModel):
    items: list[TicketRead]
    total: int
    page: int
    page_size: int