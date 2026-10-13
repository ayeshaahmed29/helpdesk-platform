from pydantic import BaseModel, Field


class SlaSettings(BaseModel):
    first_reply_hours: int


class SlaSettingsUpdate(BaseModel):
    first_reply_hours: int = Field(ge=1, le=168)