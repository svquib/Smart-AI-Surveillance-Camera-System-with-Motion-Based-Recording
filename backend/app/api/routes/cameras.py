from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.camera import Camera
from app.models.user import User
from app.schemas.camera import CameraCreate, CameraOut

router = APIRouter(prefix="/cameras", tags=["cameras"])


@router.get("", response_model=list[CameraOut])
def list_cameras(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Camera).order_by(Camera.id).all()


@router.post("", response_model=CameraOut, status_code=201)
def add_camera(
    payload: CameraCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    cam = Camera(**payload.model_dump())
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam


@router.get("/{camera_id}", response_model=CameraOut)
def get_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    return cam
