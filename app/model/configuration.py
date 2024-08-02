from pydantic import BaseModel


class AppConfiguration(BaseModel):
    id: str
    min_support: int
    constraint_levels: list
    constraint_types: list
    unary: bool
    binary: bool
