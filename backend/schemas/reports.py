from datetime import date

from pydantic import BaseModel


class TicketsPerDayItem(BaseModel):
    day: date
    count: int


class TicketsPerDayResponse(BaseModel):
    items: list[TicketsPerDayItem]


class AvgFirstResponseResponse(BaseModel):
    average_hours: float | None
    ticket_count: int