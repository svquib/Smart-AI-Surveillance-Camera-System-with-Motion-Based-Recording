from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CameraCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    location: Optional[str] = None
    source: str = "0"          # "0" = webcam, or an rtsp:// URL
    status: str = "active"


class CameraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    location: Optional[str]
    source: str
    status: str
    created_at: datetime
