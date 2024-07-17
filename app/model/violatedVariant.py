from typing import Dict, List

from pydantic import BaseModel

from app.model.variant import Variant


class ViolatedVariant(BaseModel):
    id: str
    variant: Variant
    activities: Dict[str, List[str]]