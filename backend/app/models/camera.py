from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.db.session import Base


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    location = Column(String(255), nullable=True)
    # "0" for the laptop webcam, or an rtsp:// URL for an IP cam
    source = Column(String(512), nullable=False, default="0")
    status = Column(String(20), nullable=False, default="active")  # active | inactive
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    events = relationship("Event", back_populates="camera", cascade="all, delete-orphan")
