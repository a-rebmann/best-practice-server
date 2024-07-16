from pydantic import BaseModel


class ProcessModel(BaseModel):
    id: str
    log_name: str
    log_path: str
