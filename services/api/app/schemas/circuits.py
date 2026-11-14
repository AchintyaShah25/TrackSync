from pydantic import BaseModel


class Outline(BaseModel):
    x: list[float]
    y: list[float]


class Corner(BaseModel):
    number: int
    letter: str
    x: float
    y: float
    angle: float


class Circuit(BaseModel):
    id: str
    name: str
    locality: str | None
    country: str | None
    length_m: int | None
    outline: Outline | None
    corners: list[Corner]
