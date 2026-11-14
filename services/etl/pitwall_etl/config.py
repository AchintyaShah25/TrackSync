"""ETL settings, read from the environment (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    database_url: str
    fastf1_cache: Path
    openf1_cache: Path
    openf1_max_per_minute: int

    @classmethod
    def from_env(cls) -> Settings:
        def path(var: str, default: str) -> Path:
            p = Path(os.environ.get(var, default))
            return p if p.is_absolute() else REPO_ROOT / p

        return cls(
            database_url=os.environ.get(
                "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
            ),
            fastf1_cache=path("FASTF1_CACHE", ".cache/fastf1"),
            openf1_cache=path("OPENF1_CACHE_DIR", ".cache/openf1"),
            openf1_max_per_minute=int(os.environ.get("OPENF1_MAX_PER_MINUTE", "28")),
        )


def configure_fastf1(cache_dir: Path) -> None:
    """Point FastF1 at the repo cache before any FastF1 call.

    Without this FastF1 silently uses the user-wide cache (docs/decisions/0003).
    """
    import fastf1

    cache_dir.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.configure(cache_dir=str(cache_dir))
