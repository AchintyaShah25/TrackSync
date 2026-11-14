"""Cache-Control for read-only public data. The ETL updates data at most weekly."""

from fastapi import Response

PUBLIC_DATA = "public, max-age=3600, stale-while-revalidate=86400"


def public_cache(response: Response) -> None:
    response.headers["Cache-Control"] = PUBLIC_DATA
