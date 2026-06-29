"""Phase 5 test tool — live YOLOv11 object detection overlay.

Run from `backend/` with your venv active (first run downloads yolo11n.pt):

    python scripts/preview_detection.py
    python scripts/preview_detection.py --device mps        # Apple Silicon GPU
    python scripts/preview_detection.py --conf 0.5
    python scripts/preview_detection.py --source "rtsp://user:pass@host:554/stream"

You'll see labelled boxes (label + confidence) and the category colour:
    person=green  cat/dog=yellow  vehicle=blue  other=grey

Controls:  q / ESC -> quit
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.vision.camera import CameraConfig, CameraError, VideoSource  # noqa: E402
from app.vision.detector import DetectorConfig, ObjectDetector  # noqa: E402

CATEGORY_COLORS = {
    "person": (0, 255, 0),
    "cat": (0, 255, 255),
    "dog": (0, 200, 255),
    "vehicle": (255, 128, 0),
    "other": (180, 180, 180),
}


def draw_detections(frame, detections) -> None:
    for d in detections:
        x, y, w, h = d.box
        color = CATEGORY_COLORS.get(d.category, (180, 180, 180))
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        text = f"{d.label} {d.confidence:.2f}"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(frame, (x, y - th - 6), (x + tw + 4, y), color, -1)
        cv2.putText(frame, text, (x + 2, y - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Live YOLOv11 detection (Phase 5 test).")
    p.add_argument("--source", default=settings.DEFAULT_CAMERA_SOURCE)
    p.add_argument("--model", default="yolo11n.pt")
    p.add_argument("--conf", type=float, default=0.35)
    p.add_argument("--device", default=None, help='"cpu", "mps", or "cuda:0".')
    return p.parse_args()


def main() -> int:
    args = parse_args()
    cam = VideoSource(CameraConfig(source=args.source))
    detector = ObjectDetector(
        DetectorConfig(model_path=args.model, conf_threshold=args.conf, device=args.device)
    )

    print("Loading model (first run downloads weights)...")
    detector.load()

    try:
        cam.open()
    except CameraError as exc:
        print(f"ERROR: {exc}")
        return 1

    window = "Phase 5 - YOLOv11 Detection (q to quit)"
    frames, t0, fps = 0, time.time(), 0.0

    try:
        while True:
            frame = cam.read()
            if frame is None:
                if not cam.is_open:
                    break
                continue

            detections = detector.detect(frame)
            draw_detections(frame, detections)

            frames += 1
            if frames % 10 == 0:
                now = time.time()
                fps = 10.0 / (now - t0)
                t0 = now

            best = detector.best(detections)
            summary = f"{best.category}/{best.label} {best.confidence:.2f}" if best else "-"
            cv2.rectangle(frame, (0, 0), (frame.shape[1], 36), (30, 30, 30), -1)
            cv2.putText(frame, f"{fps:4.1f} FPS  objects={len(detections)}  top={summary}",
                        (12, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            cv2.imshow(window, frame)
            if (cv2.waitKey(1) & 0xFF) in (ord("q"), 27):
                break
    finally:
        cam.release()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
