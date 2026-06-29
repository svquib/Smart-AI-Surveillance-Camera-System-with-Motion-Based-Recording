from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True, index=True)

    type = Column(String(20), nullable=False, default="info")    # info|suspicious|emergency
    message = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="new")   # new|acknowledged|resolved
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    event = relationship("Event", back_populates="alerts")
