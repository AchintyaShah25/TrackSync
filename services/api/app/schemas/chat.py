"""Chat request/response bodies (SPEC M3, decisions 0029, 0032)."""

from typing import Literal

from pydantic import BaseModel, Field

MAX_HISTORY = 12
MAX_MESSAGE_CHARS = 2000


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS * 2)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)
    level: Literal["beginner", "expert"] = "beginner"


class SourceOut(BaseModel):
    n: int
    title: str
    section: str | None
    url: str | None
    license: str
    source: Literal["fia", "wikipedia", "summary"]
    excerpt: str


class ChartSeries(BaseModel):
    name: str
    points: list[list[float | int | str]]  # [x, y]; x is a number (line) or label (bar)


class ChartSpec(BaseModel):
    type: Literal["line", "bar"]
    title: str
    x_label: str
    y_label: str
    series: list[ChartSeries]


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceOut]  # only passages the answer cites
    charts: list[ChartSpec]
    tools_used: list[str]
    provider: str
    model: str
