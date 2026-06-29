from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.session import Base


class Event(Base):
    """One recorded incident: what was seen, what they were doing, and the clip."""

    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=True, index=True)

    object = Column(String(50), nullable=True)      # category: person/cat/dog/vehicle/other
    label = Column(String(50), nullable=True)       # exact YOLO label, e.g. "car"
    confidence = Column(Float, nullable=True)
    activity = Column(String(30), nullable=True)    # standing/walking/running/falling/...

    video_path = Column(String(512), nullable=True)
    snapshot_path = Column(String(512), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    camera = relationship("Camera", back_populates="events")
    alerts = relationship("Alert", back_populates="event", cascade="all, delete-orphan")
