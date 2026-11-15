from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ..auth import User, current_user
from ..schemas.me import Preferences, SavedItem, SavedItemIn
from ..services import me as service

router = APIRouter(prefix="/me", tags=["me"])
Me = Annotated[User, Depends(current_user)]


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


async def _call(fn, *args):
    try:
        return await fn(*args)
    except service.MeError as err:
        raise HTTPException(err.status, err.detail) from err


@router.get("/preferences", response_model=Preferences)
async def get_preferences(request: Request, response: Response, user: Me):
    _private(response)
    return await _call(service.get_preferences, request.app.state.engine, user)


@router.put("/preferences", response_model=Preferences)
async def put_preferences(body: Preferences, request: Request, response: Response, user: Me):
    _private(response)
    return await _call(service.put_preferences, request.app.state.engine, user, body)


@router.get("/saved", response_model=list[SavedItem])
async def list_saved(request: Request, response: Response, user: Me):
    _private(response)
    return await _call(service.list_saved, request.app.state.engine, user)


@router.post("/saved", response_model=SavedItem, status_code=201)
async def add_saved(body: SavedItemIn, request: Request, response: Response, user: Me):
    _private(response)
    return await _call(service.add_saved, request.app.state.engine, user, body)


@router.delete("/saved/{item_id}", status_code=204)
async def delete_saved(item_id: UUID, request: Request, user: Me):
    await _call(service.delete_saved, request.app.state.engine, user, item_id)
    return Response(status_code=204)
