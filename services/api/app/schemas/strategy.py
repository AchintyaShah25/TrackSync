"""Strategy forecaster request/response bodies (SPEC M2, decision 0021)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .common import DriverRef

Compound = Literal["SOFT", "MEDIUM", "HARD"]
SafetyCars = Literal["random", "actual"]
MAX_STRATEGIES = 3


class StintIn(BaseModel):
    compound: Compound
    laps: int = Field(ge=1, le=100)


class StrategyIn(BaseModel):
    label: str = Field(min_length=1, max_length=40)
    stints: list[StintIn] = Field(min_length=1, max_length=5)


class SimulateRequest(BaseModel):
    event_id: int
    driver_id: str = Field(min_length=1, max_length=40)
    strategies: list[StrategyIn] = Field(min_length=1, max_length=MAX_STRATEGIES)
    runs: int = Field(default=500, ge=100, le=1000)
    seed: int = Field(default=0, ge=0, le=2**31 - 1)
    safety_cars: SafetyCars = "random"


class Percentiles(BaseModel):
    p5: float
    p25: float
    p50: float
    p75: float
    p95: float


class GapBands(BaseModel):
    """Per-lap gap to the driver's actual strategy, seconds (positive = behind). Index = lap - 1."""

    p10: list[float]
    p25: list[float]
    p50: list[float]
    p75: list[float]
    p90: list[float]


class PositionProb(BaseModel):
    position: int
    p: float


class StrategyOut(BaseModel):
    label: str
    stints: list[StintIn]
    stop_laps: list[int]
    finish_delta_s: Percentiles  # finish time vs the actual strategy (negative = faster)
    gap: GapBands
    positions: list[PositionProb] | None  # None when the driver was not on the lead lap
    p_gain: float | None  # P(finishing ahead of the actual result)
    p_lose: float | None


class ActualOut(BaseModel):
    stints: list[StintIn]
    stop_laps: list[int]
    position: int | None  # official classification
    model_position: int | None  # rank of the actual race time among lead-lap finishers
    race_time_s: float | None


class ModelInfo(BaseModel):
    version: int
    n_races: int
    sigma: float
    pit_loss: float
    sc_rate: float
    vsc_rate: float


class SimulateResponse(BaseModel):
    event_id: int
    driver: DriverRef
    total_laps: int
    runs: int
    seed: int
    safety_cars: SafetyCars
    actual: ActualOut
    strategies: list[StrategyOut]
    sc_share: list[float]  # share of runs under SC on each lap
    vsc_share: list[float]
    model: ModelInfo


class DegCurve(BaseModel):
    compound: Compound
    offset: float  # vs SOFT, seconds
    age: list[int]
    seconds: list[float]  # time lost to tyre age


class ModelSummary(BaseModel):
    circuit_id: str
    version: int
    n_races: int
    n_laps: int
    fitted_at: datetime
    sigma: float
    trend: float  # seconds per lap (fuel burn + track evolution)
    pit_loss: float
    pit_loss_sd: float
    sc_rate: float
    vsc_rate: float
    curves: list[DegCurve]
