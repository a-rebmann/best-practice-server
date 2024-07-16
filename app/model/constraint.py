from pydantic import BaseModel


class Constraint(BaseModel):
    id: str
    constraint_type: str
    constraint_str: str
    arity: str
    level: str
    left_operand: str
    right_operand: str
    object_type: str
    processmodel_id: str
    support: int
