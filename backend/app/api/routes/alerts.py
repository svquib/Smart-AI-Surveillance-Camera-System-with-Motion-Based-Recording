from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.alert import Alert
from app.models.user import User
from app.schemas.alert import AlertCreate, AlertOut, AlertUpdate

router = APIRouter(prefix="/alerts", tags=["alerts"])


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
    # For now this just records the alert. Phase 10 hooks Telegram in right here.
    alert = Alert(**payload.model_dump())
    db.add(alert)
    db.commit()
    db.refresh(alert)
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
