from pydantic import BaseModel


class Variant(BaseModel):
    id: str
    log: str
    activities: list[str]
    frequency: int
    cases: list[str]
