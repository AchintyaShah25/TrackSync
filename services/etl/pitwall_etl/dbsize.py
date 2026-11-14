"""Print database and per-table sizes (make db-size). Budget: keep the DB well under 400 MB."""

from __future__ import annotations

from sqlalchemy import text

from .config import Settings
from .load.db import make_engine

QUERY = text(
    """
    select c.relname as table,
           pg_total_relation_size(c.oid) as bytes,
           c.reltuples::bigint as approx_rows
    from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relkind = 'r'
    order by bytes desc
    """
)


def main() -> None:
    engine = make_engine(Settings.from_env().database_url)
    with engine.connect() as conn:
        conn.execute(text("analyze"))  # refresh reltuples so row estimates are current
        total = conn.execute(text("select pg_database_size(current_database())")).scalar_one()
        print(f"{'table':<22}{'size':>12}{'rows':>12}")
        for name, size, rows in conn.execute(QUERY):
            print(f"{name:<22}{size / 1e6:>10.2f}MB{max(rows, 0):>12}")
        print(f"{'database total':<22}{total / 1e6:>10.2f}MB")


if __name__ == "__main__":
    main()
