"""Signed-in user's preferences and saved items (SPEC M3, decision 0030)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

MAX_SAVED = 100
MAX_PINNED = 6


class Preferences(BaseModel):
    favorite_driver_id: str | None = Field(default=None, max_length=40)
    favorite_team_id: str | None = Field(default=None, max_length=40)
    theme: Literal["light", "dark", "system"] | None = None
    units: Literal["metric", "imperial"] = "metric"
    chat_level: Literal["beginner", "expert"] = "beginner"
    home_widgets: list[UUID] = Field(default_factory=list, max_length=MAX_PINNED)


class SavedItemIn(BaseModel):
    kind: Literal["chart", "strategy"]
    title: str = Field(min_length=1, max_length=120)
    path: str = Field(min_length=1, max_length=500)

    @field_validator("path")
    @classmethod
    def site_path(cls, v: str) -> str:
        # Saved items are links back into this site only (no open redirects, no javascript:).
        if not v.startswith("/") or v.startswith("//") or "\\" in v:
            raise ValueError("must be a path on this site, like /races/2024/16/forecast")
        return v


class SavedItem(SavedItemIn):
    id: UUID
    created_at: datetime
