"""Persist a finished clip as an Event (+ any Alerts) in the database.

The live pipeline calls record_event() once per saved clip. I write straight
to the DB with a SQLAlchemy session rather than POSTing to the API — the
pipeline runs on the same box, so there's no point round-tripping through HTTP
and auth just to insert a row.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.alert import Alert
from app.models.event import Event
from app.services.decision import DecisionContext, DecisionEngine

logger = get_logger(__name__)
_engine = DecisionEngine()


def record_event(
    db: Session,
    *,
    camera_id: Optional[int],
    camera_name: str,
    object_counts: Dict[str, int],
    top_object: Optional[str],
    confidence: Optional[float],
    activity: str,
    video_path: Optional[str],
    snapshot_path: Optional[str],
    when: Optional[datetime] = None,
) -> Event:
    when = when or datetime.utcnow()

    event = Event(
        camera_id=camera_id,
        object=top_object,
        label=top_object,        # we summarise to category; exact label optional
        confidence=confidence,
        activity=activity,
        video_path=video_path,
        snapshot_path=snapshot_path,
        timestamp=when,
    )
    db.add(event)
    db.flush()  # assigns event.id without committing yet

    # Run the rules and attach any alerts to this event.
    drafts = _engine.evaluate(DecisionContext(
        object_counts=object_counts,
        activity=activity,
        when=when,
        camera_name=camera_name,
    ))
    for d in drafts:
        db.add(Alert(event_id=event.id, type=d.type, message=d.message, status="new"))

    db.commit()
    db.refresh(event)

    if drafts:
        logger.info("Event %d saved with %d alert(s): %s",
                    event.id, len(drafts), [d.type for d in drafts])
    else:
        logger.info("Event %d saved (no alerts)", event.id)
    return event
