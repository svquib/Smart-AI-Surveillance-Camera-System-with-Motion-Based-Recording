from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class EventCreate(BaseModel):
    camera_id: Optional[int] = None
    object: Optional[str] = None
    label: Optional[str] = None
    confidence: Optional[float] = None
    activity: Optional[str] = None
    video_path: Optional[str] = None
    snapshot_path: Optional[str] = None


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: Optional[int]
    object: Optional[str]
    label: Optional[str]
    confidence: Optional[float]
    activity: Optional[str]
    video_path: Optional[str]
    snapshot_path: Optional[str]
    timestamp: datetime
