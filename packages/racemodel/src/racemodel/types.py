"""Shared types, constants and strategy validation (decision 0020)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

# Bump when the fitted parameters change meaning. Rows in circuit_model_params are keyed by
# it, so a refit with new logic never overwrites what a running API reads (decision 0022).
MODEL_VERSION = 1

DRY_COMPOUNDS: tuple[str, ...] = ("SOFT", "MEDIUM", "HARD")
COMPOUND_INDEX = {c: i for i, c in enumerate(DRY_COMPOUNDS)}

MAX_STINTS = 5


@dataclass(frozen=True)
class Stint:
    compound: str
    laps: int


@dataclass
class PaceParams:
    """Lap-time model for one circuit (seconds).

    lap_time = intercept + offset[c] + deg1[c]*age + deg2[c]*age^2 + trend*lap + noise.
    `offset` is relative to SOFT (offset[SOFT] = 0). `trend` combines fuel burn and track
    evolution, which are both linear in lap and cannot be told apart.
    """

    offset: list[float]
    deg1: list[float]
    deg2: list[float]
    trend: float
    sigma: float
    age_max: list[int]

    def coef_vector(self) -> list[float]:
        return [*self.offset[1:], *self.deg1, *self.deg2, self.trend]

    @classmethod
    def from_coef_vector(cls, beta: list[float], sigma: float, age_max: list[int]) -> PaceParams:
        return cls(
            offset=[0.0, beta[0], beta[1]],
            deg1=list(beta[2:5]),
            deg2=list(beta[5:8]),
            trend=beta[8],
            sigma=sigma,
            age_max=list(age_max),
        )


@dataclass
class EventParams:
    """Neutralizations and pit stops for one circuit (decision 0021)."""

    sc_rate: float  # expected SC deployments per race
    vsc_rate: float  # expected VSC deployments per race
    pit_loss: float  # seconds lost by a green-flag stop (in-lap + out-lap)
    pit_loss_sd: float
    sc_pit_factor: float = 0.5  # share of the pit loss paid when stopping under SC
    vsc_pit_factor: float = 0.65
    sc_lap_extra: float = 30.0  # seconds added to every car's lap under SC
    vsc_lap_extra: float = 20.0
    # Empirical distributions pooled over all circuits.
    start_fractions: list[float] = field(default_factory=lambda: [0.1, 0.3, 0.5, 0.7])
    sc_durations: list[int] = field(default_factory=lambda: [3, 4, 5])
    vsc_durations: list[int] = field(default_factory=lambda: [1, 2, 3])


@dataclass
class CircuitParams:
    circuit_id: str
    pace: PaceParams
    events: EventParams
    model_version: int = MODEL_VERSION

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> CircuitParams:
        return cls(
            circuit_id=d["circuit_id"],
            pace=PaceParams(**d["pace"]),
            events=EventParams(**d["events"]),
            model_version=d.get("model_version", MODEL_VERSION),
        )


def validate_strategy(stints: list[Stint], total_laps: int) -> list[str]:
    """Return human-readable problems with a dry-race strategy (empty list = valid)."""
    errors: list[str] = []
    if not stints:
        return ["add at least one stint"]
    if len(stints) > MAX_STINTS:
        errors.append(f"at most {MAX_STINTS} stints")
    for i, s in enumerate(stints, start=1):
        if s.compound not in COMPOUND_INDEX:
            errors.append(f"stint {i}: compound must be one of {', '.join(DRY_COMPOUNDS)}")
        if s.laps < 1:
            errors.append(f"stint {i}: needs at least 1 lap")
    laps = sum(s.laps for s in stints)
    if laps != total_laps:
        errors.append(f"stints cover {laps} laps; the race is {total_laps} laps")
    if len({s.compound for s in stints}) < 2:
        errors.append("a dry race must use at least two different compounds")
    return errors
