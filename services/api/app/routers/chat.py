from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncConnection

from ..auth import User, optional_user
from ..db import get_conn
from ..llm import AllProvidersDown, embed_query
from ..schemas.chat import ChatRequest, ChatResponse
from ..services.chat import agent

router = APIRouter(tags=["chat"])
Conn = Annotated[AsyncConnection, Depends(get_conn)]


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Ask the F1 assistant (guests allowed, with stricter limits)",
)
async def chat(
    body: ChatRequest,
    request: Request,
    conn: Conn,
    user: Annotated[User | None, Depends(optional_user)],
):
    chain = request.app.state.llm
    if not chain.configured:
        raise HTTPException(503, "chat is not configured on this server yet")
    await request.app.state.chat_limiter.check(request.app.state.engine, request, user)
    key = request.app.state.settings.gemini_api_key
    transport = request.app.state.embed_transport

    async def embed(q: str):
        return await embed_query(q, key, transport)

    try:
        return await agent.answer(conn, chain, embed, body)
    except AllProvidersDown as err:
        secs = str(max(1, int(err.retry_after)))
        raise HTTPException(
            503, "the assistant is busy right now; try again shortly", headers={"Retry-After": secs}
        ) from err
