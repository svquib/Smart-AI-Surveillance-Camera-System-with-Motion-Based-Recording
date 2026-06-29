from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.event import Event
from app.models.user import User
from app.schemas.event import EventCreate, EventOut

logger = get_logger(__name__)

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[EventOut])
def list_events(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    camera_id: int | None = None,
    activity: str | None = None,
    limit: int = Query(50, le=500),
    offset: int = 0,
):
    q = db.query(Event)
    if camera_id is not None:
        q = q.filter(Event.camera_id == camera_id)
    if activity:
        q = q.filter(Event.activity == activity)
    return q.order_by(Event.timestamp.desc()).offset(offset).limit(limit).all()


@router.post("", response_model=EventOut, status_code=201)
def create_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    # The vision pipeline (Phase 8) posts here when it saves a clip.
    event = Event(**payload.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("/{event_id}", response_model=EventOut)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.delete("/{event_id}", status_code=204)
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Delete an event, its alerts (cascade), and the files on disk."""
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Remove the clip, snapshot, and the .json sidecar next to the clip.
    to_remove = [event.video_path, event.snapshot_path]
    if event.video_path:
        to_remove.append(str(Path(event.video_path).with_suffix(".json")))
    for p in to_remove:
        if not p:
            continue
        try:
            Path(p).unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Could not delete %s: %s", p, exc)

    db.delete(event)  # alerts go with it via cascade
    db.commit()
    return Response(status_code=204)
