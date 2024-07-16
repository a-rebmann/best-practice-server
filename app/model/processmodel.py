from pydantic import BaseModel


class ProcessModel(BaseModel):
    id: str
    processmodel_name: str
    json_str: str
