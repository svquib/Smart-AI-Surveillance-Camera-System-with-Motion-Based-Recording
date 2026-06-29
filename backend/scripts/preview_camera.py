"""Phase 2 test tool — open a live camera window to verify the connection.

Run from the `backend/` folder with your venv active:

    # Laptop webcam (default index 0)
    python scripts/preview_camera.py

    # A specific webcam index
    python scripts/preview_camera.py --source 1

    # An IP camera / RTSP stream
    python scripts/preview_camera.py --source "rtsp://user:pass@192.168.1.10:554/stream1"

Controls:
    q  or  ESC   -> quit
    s            -> save a snapshot to storage/snapshots/

This script depends only on the VideoSource class so it doubles as a real
integration test of Phase 2's camera layer.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

# Make `app` importable when running this file directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.vision.camera import CameraConfig, CameraError, VideoSource  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Live camera preview (Phase 2 test).")
    p.add_argument(
        "--source",
        default=settings.DEFAULT_CAMERA_SOURCE,
        help="Webcam index (e.g. 0) or RTSP/HTTP URL. Default from .env.",
    )
    p.add_argument("--width", type=int, default=None, help="Requested capture width.")
    p.add_argument("--height", type=int, default=None, help="Requested capture height.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    config = CameraConfig(source=args.source, width=args.width, height=args.height)

    settings.SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    window = "Phase 2 - Camera Preview (q/ESC to quit, s to snapshot)"

    print(f"Connecting to source: {args.source!r} ...")
    try:
        cam = VideoSource(config)
        cam.open()
    except CameraError as exc:
        print(f"ERROR: {exc}")
        print("Tips: is the webcam in use by another app? "
              "For macOS, grant Terminal camera access in "
              "System Settings > Privacy & Security > Camera.")
        return 1

    # Simple FPS counter for sanity-checking the stream.
    frames_seen, t0 = 0, time.time()
    fps = 0.0

    try:
        while True:
            frame = cam.read()
            if frame is None:
                # transient miss; keep trying
                if not cam.is_open:
                    print("Camera source lost and could not reconnect.")
                    break
                continue

            frames_seen += 1
            if frames_seen % 10 == 0:
                now = time.time()
                fps = 10.0 / (now - t0)
                t0 = now

            cv2.putText(
                frame, f"{fps:4.1f} FPS", (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2,
            )
            cv2.imshow(window, frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):  # q or ESC
                break
            if key == ord("s"):
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                out = settings.SNAPSHOTS_DIR / f"snapshot_{ts}.jpg"
                cv2.imwrite(str(out), frame)
                print(f"Saved snapshot -> {out}")
    finally:
        cam.release()
        cv2.destroyAllWindows()

    print("Preview closed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
