from datetime import datetime

from pydantic import BaseModel


class Season(BaseModel):
    year: int
    events: int
    completed: int


class EventSession(BaseModel):
    code: str
    name: str
    start_utc: datetime


class EventSummary(BaseModel):
    id: int
    season: int
    round: int
    name: str
    slug: str
    format: str
    circuit_id: str
    circuit_name: str
    locality: str | None
    country: str | None
    race_start_utc: datetime | None
    sessions: list[EventSession]
    has_data: bool
