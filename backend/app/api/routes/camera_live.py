"""Live MJPEG stream for the dashboard.

This opens a camera and pushes JPEG frames as multipart/x-mixed-replace, which
an <img> tag can render directly — the simplest way to get a live feed into the
browser without WebRTC.

Two honest caveats:
  - It's left unauthenticated because an <img src> can't send a Bearer header.
    Fine for localhost; put it behind a token-in-query or a proxy before
    exposing it anywhere real.
  - It grabs the camera for itself, so don't run this at the same time as
    run_surveillance.py on the same device — they'll fight over the webcam.
"""

import cv2
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.logging import get_logger
from app.vision.camera import CameraConfig, CameraError, VideoSource

logger = get_logger(__name__)
router = APIRouter(prefix="/camera", tags=["camera"])

BOUNDARY = "frame"


def _mjpeg_generator(source: str):
    cam = VideoSource(CameraConfig(source=source))
    try:
        cam.open()
    except CameraError as exc:
        logger.error("Live stream could not open %r: %s", source, exc)
        return

    try:
        for frame in cam.frames():
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ok:
                continue
            yield (
                b"--" + BOUNDARY.encode() + b"\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"
            )
    finally:
        cam.release()  # runs when the browser disconnects


@router.get("/live")
def live(source: str = Query(default=None, description="Webcam index or RTSP URL")):
    src = source if source is not None else settings.DEFAULT_CAMERA_SOURCE
    return StreamingResponse(
        _mjpeg_generator(src),
        media_type=f"multipart/x-mixed-replace; boundary={BOUNDARY}",
    )
