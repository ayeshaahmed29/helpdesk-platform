from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

Body = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)]


class CommentCreate(BaseModel):
    body: Body
    is_internal: bool = False


class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    author_id: int
    body: str
    is_internal: bool
    created_at: datetime