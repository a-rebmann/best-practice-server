from pydantic import BaseModel

from app.model.fittedConstraint import FittedConstraint


class Violation(BaseModel):
    id: str
    log: str
    constraint: FittedConstraint
    cases: list[str]
    frequency: int
