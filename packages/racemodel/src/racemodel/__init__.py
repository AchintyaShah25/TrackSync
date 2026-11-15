"""Shared race model: the ETL fits parameters, the API simulates (decisions 0020, 0021).

Rule: pure Python + NumPy only. No web, DB, or FastF1 imports.
"""

from .events import LapRow, Period, RaceSummary, fit_events, periods, race_sequence, stop_losses
from .fit import LapSet, driver_intercept, fit_pace, predict_offsets
from .simulate import DEFAULT_RUNS, SimResult, simulate
from .types import (
    DRY_COMPOUNDS,
    MODEL_VERSION,
    CircuitParams,
    EventParams,
    PaceParams,
    Stint,
    validate_strategy,
)

__version__ = "0.2.0"

__all__ = [
    "DEFAULT_RUNS",
    "DRY_COMPOUNDS",
    "MODEL_VERSION",
    "CircuitParams",
    "EventParams",
    "LapRow",
    "LapSet",
    "PaceParams",
    "Period",
    "RaceSummary",
    "SimResult",
    "Stint",
    "driver_intercept",
    "fit_events",
    "fit_pace",
    "periods",
    "predict_offsets",
    "race_sequence",
    "simulate",
    "stop_losses",
    "validate_strategy",
]
