from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    comment_id: int | None
    uploader_id: int
    filename: str
    content_type: str
    size: int
    created_at: datetime