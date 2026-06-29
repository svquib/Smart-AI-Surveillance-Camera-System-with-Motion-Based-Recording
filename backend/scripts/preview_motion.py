"""Phase 3 test tool — visualise motion detection live.

Run from `backend/` with your venv active:

    # Webcam, default MOG2 background subtraction
    python scripts/preview_motion.py

    # Frame-differencing method instead
    python scripts/preview_motion.py --method diff

    # IP camera
    python scripts/preview_motion.py --source "rtsp://user:pass@host:554/stream"

What you'll see:
    - Green boxes around moving regions
    - A status banner: MOTION (red) or IDLE (green)
    - The live motion "score" (total moving area in pixels)
    - A second window showing the raw foreground mask

Controls:
    q / ESC  -> quit
    m        -> toggle the mask window
    r        -> reset the detector (relearn the background)

Use the score readout to tune MOTION_THRESHOLD in your .env for your scene.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.vision.camera import CameraConfig, CameraError, VideoSource  # noqa: E402
from app.vision.motion import MotionConfig, MotionDetector  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Live motion detection (Phase 3 test).")
    p.add_argument("--source", default=settings.DEFAULT_CAMERA_SOURCE,
                   help="Webcam index or RTSP/HTTP URL. Default from .env.")
    p.add_argument("--method", choices=["mog2", "diff"], default="mog2",
                   help="Detection method. Default: mog2.")
    p.add_argument("--threshold", type=int, default=settings.MOTION_THRESHOLD,
                   help="Motion area threshold. Default from .env.")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    cam = VideoSource(CameraConfig(source=args.source))
    detector = MotionDetector(
        MotionConfig(method=args.method, motion_threshold=args.threshold)
    )

    try:
        cam.open()
    except CameraError as exc:
        print(f"ERROR: {exc}")
        return 1

    window = "Phase 3 - Motion Detection (q quit, m mask, r reset)"
    show_mask = True

    try:
        while True:
            frame = cam.read()
            if frame is None:
                if not cam.is_open:
                    print("Camera lost.")
                    break
                continue

            result = detector.process(frame)

            # Draw moving regions.
            for (x, y, w, h) in result.boxes:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

            # Status banner.
            label = "MOTION" if result.motion else "IDLE"
            color = (0, 0, 255) if result.motion else (0, 200, 0)
            cv2.rectangle(frame, (0, 0), (frame.shape[1], 36), (30, 30, 30), -1)
            cv2.putText(frame, f"{label}  score={result.score}  method={args.method}",
                        (12, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            cv2.imshow(window, frame)
            if show_mask and result.mask is not None:
                cv2.imshow("Foreground mask", result.mask)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("m"):
                show_mask = not show_mask
                if not show_mask:
                    cv2.destroyWindow("Foreground mask")
            if key == ord("r"):
                detector.reset()
                print("Detector reset.")
    finally:
        cam.release()
        cv2.destroyAllWindows()

    print("Preview closed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
