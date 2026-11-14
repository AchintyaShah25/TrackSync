import json
from pathlib import Path

import pandas as pd
import pytest

FIXTURES = Path(__file__).parent / "fixtures"
TIMEDELTA_COLUMNS = ("Q1", "Q2", "Q3", "totalRaceTime", "fastestLapTime")
DATE_COLUMNS = ("raceDate", "fp1Date", "fp2Date", "fp3Date", "qualifyingDate", "sprintDate")


def load_frame(name: str) -> pd.DataFrame:
    """Load a recorded Jolpica frame, restoring the dtypes FastF1 produces."""
    df = pd.DataFrame(json.loads((FIXTURES / name).read_text()))
    for col in TIMEDELTA_COLUMNS:
        if col in df:
            df[col] = pd.to_timedelta(df[col], unit="s")
    for col in DATE_COLUMNS:
        if col in df:
            df[col] = pd.to_datetime(df[col])
    return df


@pytest.fixture
def fixture_frame():
    return load_frame


@pytest.fixture
def fixture_json():
    return lambda name: json.loads((FIXTURES / name).read_text())
