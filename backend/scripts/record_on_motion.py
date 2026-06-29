"""Phase 4 — the first end-to-end surveillance loop.

Camera ──► Motion detector ──► Recorder
                 │                   │
            (gates AI work)    (saves clips only when motion,
                                with pre-roll + cooldown)

Run from `backend/` with your venv active:

    python scripts/record_on_motion.py
    python scripts/record_on_motion.py --source "rtsp://user:pass@host:554/stream"
    python scripts/record_on_motion.py --no-window      # headless (server) mode

Clips land in   storage/recordings/<camera>_<timestamp>.mp4
A snapshot + a .json metadata sidecar are saved alongside each clip.

Controls (windowed mode):
    q / ESC -> quit (finalises any in-progress clip first)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.vision.camera import CameraConfig, CameraError, VideoSource  # noqa: E402
from app.vision.motion import MotionConfig, MotionDetector  # noqa: E402
from app.services.recorder import MotionRecorder, RecorderConfig  # noqa: E402

logger = get_logger("record_on_motion")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Motion-based recording (Phase 4).")
    p.add_argument("--source", default=settings.DEFAULT_CAMERA_SOURCE,
                   help="Webcam index or RTSP/HTTP URL. Default from .env.")
    p.add_argument("--method", choices=["mog2", "diff"], default="mog2")
    p.add_argument("--threshold", type=int, default=settings.MOTION_THRESHOLD)
    p.add_argument("--fps", type=int, default=20, help="FPS written into clips.")
    p.add_argument("--camera-name", default="camera-1")
    p.add_argument("--no-window", action="store_true",
                   help="Run headless (no preview window).")
    return p.parse_args()


def main() -> int:
    configure_logging()
    args = parse_args()

    cam = VideoSource(CameraConfig(source=args.source))
    detector = MotionDetector(
        MotionConfig(method=args.method, motion_threshold=args.threshold)
    )
    recorder = MotionRecorder(
        RecorderConfig(fps=args.fps, camera_name=args.camera_name)
    )

    try:
        cam.open()
    except CameraError as exc:
        logger.error("%s", exc)
        return 1

    window = "Phase 4 - Recording on Motion (q to quit)"
    logger.info("Surveillance loop running. Move in front of the camera to trigger a clip.")

    try:
        while True:
            frame = cam.read()
            if frame is None:
                if not cam.is_open:
                    logger.error("Camera lost.")
                    break
                continue

            result = detector.process(frame)
            meta = recorder.feed(frame, motion=result.motion, score=result.score)
            if meta:
                logger.info("CLIP SAVED -> %s (%.1fs)",
                            Path(meta.video_path).name, meta.duration_seconds)

            if not args.no_window:
                for (x, y, w, h) in result.boxes:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                rec = recorder.is_recording
                label = "REC ●" if rec else ("MOTION" if result.motion else "IDLE")
                color = (0, 0, 255) if rec else ((0, 165, 255) if result.motion else (0, 200, 0))
                cv2.rectangle(frame, (0, 0), (frame.shape[1], 36), (30, 30, 30), -1)
                cv2.putText(frame, f"{label}  score={result.score}",
                            (12, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                cv2.imshow(window, frame)
                if (cv2.waitKey(1) & 0xFF) in (ord("q"), 27):
                    break
    finally:
        final = recorder.flush()  # finalise an in-progress clip cleanly
        if final:
            logger.info("Finalised clip on exit -> %s", Path(final.video_path).name)
        cam.release()
        cv2.destroyAllWindows()

    logger.info("Stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
