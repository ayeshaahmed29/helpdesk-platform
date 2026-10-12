from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditLogItem(BaseModel):
    id: int
    action: str
    actor_user_id: int | None
    # Full name of the actor (email if there is no name). None = the system did it.
    actor_name: str | None
    entity_type: str | None
    entity_id: int | None
    metadata: dict[str, Any]
    created_at: datetime


class AuditLogPage(BaseModel):
    items: list[AuditLogItem]
    total: int
    page: int
    page_size: int