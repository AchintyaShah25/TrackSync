from pydantic import BaseModel

from .common import DriverRef


class DriverStanding(BaseModel):
    position: int | None
    driver: DriverRef
    points: float
    wins: int


class ConstructorStanding(BaseModel):
    position: int | None
    team_id: str
    team_name: str
    color_hex: str | None
    points: float
    wins: int


class StandingsResponse(BaseModel):
    season: int
    after_round: int
    drivers: list[DriverStanding]
    constructors: list[ConstructorStanding]
