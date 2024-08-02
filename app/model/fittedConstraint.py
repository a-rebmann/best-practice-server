from pydantic import BaseModel

from app.model.constraint import Constraint


class FittedConstraint(BaseModel):
    id: str
    log: str
    constraint_str: str
    left_operand: str
    right_operand: str
    object_type: str
    similarity: dict
    relevance: float
    constraint: Constraint
