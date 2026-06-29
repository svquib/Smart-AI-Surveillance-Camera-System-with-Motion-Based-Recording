from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.alert import Alert
from app.models.event import Event
from app.models.user import User
from app.schemas.alert import AlertCreate, AlertOut, AlertUpdate
from app.services.telegram import TelegramNotifier

router = APIRouter(prefix="/alerts", tags=["alerts"])
_notifier = TelegramNotifier()


@router.get("", response_model=list[AlertOut])
def list_alerts(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    status: str | None = None,
    type: str | None = None,
):
    q = db.query(Alert)
    if status:
        q = q.filter(Alert.status == status)
    if type:
        q = q.filter(Alert.type == type)
    return q.order_by(Alert.created_at.desc()).all()


@router.post("/send", response_model=AlertOut, status_code=201)
def send_alert(
    payload: AlertCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Record an alert and push it to Telegram (if configured)."""
    alert = Alert(**payload.model_dump())
    db.add(alert)
    db.commit()
    db.refresh(alert)

    # If it's tied to an event, grab that event's snapshot/clip to attach.
    snapshot = video = None
    if alert.event_id:
        ev = db.get(Event, alert.event_id)
        if ev:
            snapshot, video = ev.snapshot_path, ev.video_path

    _notifier.send_alert(
        alert_type=alert.type,
        message=alert.message,
        snapshot_path=snapshot,
        video_path=video,
    )
    return alert


@router.patch("/{alert_id}", response_model=AlertOut)
def update_alert(
    alert_id: int,
    payload: AlertUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = payload.status
    db.commit()
    db.refresh(alert)
    return alert
