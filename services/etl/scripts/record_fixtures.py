"""Record small, trimmed fixtures from real sources for offline tests.

Run once (needs network):
    uv run --package tracksync-etl python services/etl/scripts/record_fixtures.py
Output: services/etl/tests/fixtures/*.json. Tests never hit the network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from tracksync_etl.config import Settings, configure_fastf1
from tracksync_etl.sources import jolpica
from tracksync_etl.sources.openf1 import OpenF1Client

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
SEASON, ROUND = 2024, 16  # Monza 2024


def frame_json(df: pd.DataFrame, path: Path) -> None:
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_timedelta64_dtype(df[col]):
            df[col] = df[col].dt.total_seconds()
    path.write_text(df.to_json(orient="records", date_format="iso", indent=1))


def main() -> None:
    s = Settings.from_env()
    configure_fastf1(s.fastf1_cache)
    OUT.mkdir(parents=True, exist_ok=True)
    frame_json(jolpica.schedule(SEASON).iloc[14:17], OUT / "jolpica_schedule_2024_r15-17.json")
    frame_json(jolpica.race_results(SEASON, ROUND).head(4), OUT / "jolpica_race_2024_16_top4.json")
    frame_json(
        jolpica.qualifying_results(SEASON, ROUND).head(4), OUT / "jolpica_quali_2024_16_top4.json"
    )
    frame_json(jolpica.sprint_results(SEASON, 6).head(3), OUT / "jolpica_sprint_2024_6_top3.json")

    client = OpenF1Client(s.openf1_cache, per_minute=s.openf1_max_per_minute)
    drivers = client.get("drivers", session_key=9590)
    (OUT / "openf1_drivers_9590.json").write_text(json.dumps(drivers[:4], indent=1))


if __name__ == "__main__":
    main()
