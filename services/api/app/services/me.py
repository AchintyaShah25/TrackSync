"""User-owned data, read and written as the user so Postgres RLS applies (decision 0030).

Each call opens its own transaction, switches to the `authenticated` role and sets the JWT
claims exactly as Supabase's REST layer does. `set local` lasts only for the transaction,
so pooled connections never keep the user's identity.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from ..auth import User
from ..schemas.me import MAX_SAVED, Preferences, SavedItem, SavedItemIn

PREF_COLUMNS = "favorite_driver_id, favorite_team_id, theme, units, chat_level, home_widgets"


class MeError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


@asynccontextmanager
async def as_user(engine: AsyncEngine, user: User):
    async with engine.begin() as conn:
        await conn.execute(text("set local role authenticated"))
        await conn.execute(
            text("select set_config('request.jwt.claims', :claims, true)"),
            {"claims": json.dumps({"sub": user.id, "role": "authenticated"})},
        )
        yield conn


async def get_preferences(engine: AsyncEngine, user: User) -> Preferences:
    async with as_user(engine, user) as conn:
        row = (await conn.execute(text(f"select {PREF_COLUMNS} from user_preferences"))).first()
    return Preferences(**row._mapping) if row else Preferences()


async def put_preferences(engine: AsyncEngine, user: User, prefs: Preferences) -> Preferences:
    data = prefs.model_dump(mode="json")
    if data["favorite_driver_id"]:
        # Public reference data: checked as the service, before taking the user's role.
        async with engine.connect() as conn:
            known = await conn.scalar(
                text("select 1 from drivers where id = :d"), {"d": data["favorite_driver_id"]}
            )
        if not known:
            raise MeError(422, f"unknown driver {data['favorite_driver_id']!r}")
    async with as_user(engine, user) as conn:
        if data["home_widgets"]:
            owned = await conn.scalar(
                text("select count(*) from saved_items where id = any(cast(:ids as uuid[]))"),
                {"ids": data["home_widgets"]},
            )
            if owned != len(set(data["home_widgets"])):
                raise MeError(422, "pinned items must be your own saved items")
        await conn.execute(
            text(
                f"""
                insert into user_preferences (user_id, {PREF_COLUMNS}, updated_at)
                values (cast(:uid as uuid), :favorite_driver_id, :favorite_team_id, :theme,
                        :units, :chat_level, cast(:home_widgets as jsonb), now())
                on conflict (user_id) do update set
                  favorite_driver_id = excluded.favorite_driver_id,
                  favorite_team_id = excluded.favorite_team_id, theme = excluded.theme,
                  units = excluded.units, chat_level = excluded.chat_level,
                  home_widgets = excluded.home_widgets, updated_at = now()
                """
            ),
            {**data, "uid": user.id, "home_widgets": json.dumps(data["home_widgets"])},
        )
    return prefs


async def list_saved(engine: AsyncEngine, user: User) -> list[SavedItem]:
    async with as_user(engine, user) as conn:
        rows = (
            await conn.execute(
                text(
                    "select id, kind, title, path, created_at from saved_items "
                    "order by created_at desc limit :n"
                ),
                {"n": MAX_SAVED},
            )
        ).all()
    return [SavedItem(**r._mapping) for r in rows]


async def add_saved(engine: AsyncEngine, user: User, item: SavedItemIn) -> SavedItem:
    async with as_user(engine, user) as conn:
        count = await conn.scalar(text("select count(*) from saved_items"))
        if count >= MAX_SAVED:
            raise MeError(409, f"you can keep up to {MAX_SAVED} saved items; delete some first")
        row = (
            await conn.execute(
                text(
                    """
                    insert into saved_items (user_id, kind, title, path)
                    values (cast(:uid as uuid), :kind, :title, :path)
                    returning id, kind, title, path, created_at
                    """
                ),
                {"uid": user.id, **item.model_dump()},
            )
        ).first()
    return SavedItem(**row._mapping)


async def delete_saved(engine: AsyncEngine, user: User, item_id: UUID) -> None:
    async with as_user(engine, user) as conn:
        gone = (
            await conn.execute(text("delete from saved_items where id = :id"), {"id": item_id})
        ).rowcount
        if gone:
            # Unpin it too, so the landing page never points at a deleted item.
            await conn.execute(
                text("update user_preferences set home_widgets = home_widgets - cast(:id as text)"),
                {"id": str(item_id)},
            )
    if not gone:
        raise MeError(404, "saved item not found")
