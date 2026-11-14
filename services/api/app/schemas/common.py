from typing import Literal

from pydantic import BaseModel

RaceSession = Literal["R", "S"]
AnySession = Literal["R", "S", "Q", "SQ"]
TraceSession = Literal["Q", "R", "SQ", "S"]


class DriverRef(BaseModel):
    id: str
    code: str
    full_name: str
    number: int | None
    team_id: str | None = None
    team_name: str | None = None
    color_hex: str | None = None
