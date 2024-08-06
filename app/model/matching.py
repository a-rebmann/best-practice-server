
from datetime import datetime
from pydantic import BaseModel


class Matching(BaseModel):
    id: str
    considered_constraints: list[str]
    log_id: str
    time_of_matching: datetime