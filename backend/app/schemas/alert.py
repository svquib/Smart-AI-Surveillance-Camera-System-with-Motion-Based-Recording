from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AlertCreate(BaseModel):
    event_id: Optional[int] = None
    type: str = "info"          # info | suspicious | emergency
    message: str


class AlertUpdate(BaseModel):
    status: str                 # new | acknowledged | resolved


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: Optional[int]
    type: str
    message: str
    status: str
    created_at: datetime
