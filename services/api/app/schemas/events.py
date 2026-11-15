from pydantic import BaseModel

from .common import DriverRef
from .seasons import EventSummary


class EventDetail(EventSummary):
    drivers: list[DriverRef]
    data_sessions: list[str]  # sessions with stored results, e.g. ["Q", "R"]
    trace_sessions: list[str]  # sessions with fastest-lap traces
    total_laps: int | None


class ResultRow(BaseModel):
    position: int | None
    driver: DriverRef
    grid: int | None
    points: float
    status: str | None
    time_ms: int | None
    laps: int | None  # laps completed (race/sprint); null for qualifying


class LapRow(BaseModel):
    driver_id: str
    lap: int
    lap_time_ms: int | None
    compound: str | None
    tyre_life: int | None
    stint: int | None
    position: int | None
    pit_in: bool
    pit_out: bool
    track_status: str | None
    is_accurate: bool


class LapsPage(BaseModel):
    items: list[LapRow]
    next_cursor: str | None


class StintRow(BaseModel):
    driver_id: str
    stint: int
    compound: str | None
    start_lap: int
    end_lap: int


class StrategyResponse(BaseModel):
    session: str
    total_laps: int
    drivers: list[DriverRef]  # in finishing order
    finish_position: dict[str, int | None]
    stints: list[StintRow]


class TracePoints(BaseModel):
    d: list[float]
    speed: list[float]
    throttle: list[int]
    brake: list[int]
    gear: list[int]
    x: list[float]
    y: list[float]


class Trace(BaseModel):
    driver: DriverRef
    lap: int
    lap_time_ms: int
    points: TracePoints


class TracesResponse(BaseModel):
    event_id: int
    session: str
    circuit_id: str
    traces: list[Trace]
