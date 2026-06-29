"""Phase 5 — motion-gated detection (the efficient pipeline).

Demonstrates the core efficiency principle of the whole project:

    Camera ─► Motion? ──no──► (skip AI, ~0% load)
                   │yes
                   └──► YOLOv11 detection ─► record clip + log objects

YOLO only runs on frames that contain motion, so an empty room costs almost
nothing. This is the loop the FastAPI backend (Phase 7) will run per camera.

Run from `backend/` with your venv active:

    python scripts/detect_on_motion.py
    python scripts/detect_on_motion.py --device mps      # Apple Silicon GPU
    python scripts/detect_on_motion.py --no-window       # headless

Each saved clip's .json sidecar is augmented with the objects detected during
the event.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.vision.camera import CameraConfig, CameraError, VideoSource  # noqa: E402
from app.vision.motion import MotionConfig, MotionDetector  # noqa: E402
from app.vision.detector import DetectorConfig, ObjectDetector  # noqa: E402
from app.services.recorder import MotionRecorder, RecorderConfig  # noqa: E402

logger = get_logger("detect_on_motion")

CATEGORY_COLORS = {
    "person": (0, 255, 0), "cat": (0, 255, 255), "dog": (0, 200, 255),
    "vehicle": (255, 128, 0), "other": (180, 180, 180),
}


def draw(frame, detections):
    for d in detections:
        x, y, w, h = d.box
        color = CATEGORY_COLORS.get(d.category, (180, 180, 180))
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        cv2.putText(frame, f"{d.label} {d.confidence:.2f}", (x, y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Motion-gated YOLO detection (Phase 5).")
    p.add_argument("--source", default=settings.DEFAULT_CAMERA_SOURCE)
    p.add_argument("--threshold", type=int, default=settings.MOTION_THRESHOLD)
    p.add_argument("--conf", type=float, default=0.35)
    p.add_argument("--device", default=None)
    p.add_argument("--fps", type=int, default=20)
    p.add_argument("--detect-every", type=int, default=3,
                   help="Run YOLO every Nth motion frame (saves compute).")
    p.add_argument("--no-window", action="store_true")
    return p.parse_args()


def main() -> int:
    configure_logging()
    args = parse_args()

    cam = VideoSource(CameraConfig(source=args.source))
    motion = MotionDetector(MotionConfig(motion_threshold=args.threshold))
    detector = ObjectDetector(DetectorConfig(conf_threshold=args.conf, device=args.device))
    recorder = MotionRecorder(RecorderConfig(fps=args.fps))

    logger.info("Loading YOLO model...")
    detector.load()

    try:
        cam.open()
    except CameraError as exc:
        logger.error("%s", exc)
        return 1

    window = "Phase 5 - Detect on Motion (q to quit)"
    frame_idx = 0
    event_objects: Counter = Counter()   # accumulates objects seen during a clip
    last_detections = []

    try:
        while True:
            frame = cam.read()
            if frame is None:
                if not cam.is_open:
                    break
                continue
            frame_idx += 1

            m = motion.process(frame)

            # Only run YOLO when there is motion (and only every Nth frame).
            if m.motion and frame_idx % args.detect_every == 0:
                last_detections = detector.detect(frame)
                for d in last_detections:
                    event_objects[d.category] += 1
            elif not m.motion:
                last_detections = []

            meta = recorder.feed(frame, motion=m.motion, score=m.score)
            if meta:
                # Attach the objects observed during this event to the sidecar.
                summary = dict(event_objects)
                sidecar = Path(meta.video_path).with_suffix(".json")
                data = json.loads(sidecar.read_text())
                data["objects"] = summary
                sidecar.write_text(json.dumps(data, indent=2))
                logger.info("CLIP SAVED -> %s | objects=%s",
                            Path(meta.video_path).name, summary or "{}")
                event_objects.clear()

            if not args.no_window:
                draw(frame, last_detections)
                rec = recorder.is_recording
                label = "REC ●" if rec else ("MOTION" if m.motion else "IDLE")
                color = (0, 0, 255) if rec else ((0, 165, 255) if m.motion else (0, 200, 0))
                cv2.rectangle(frame, (0, 0), (frame.shape[1], 36), (30, 30, 30), -1)
                cv2.putText(frame, f"{label}  score={m.score}  objs={len(last_detections)}",
                            (12, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                cv2.imshow(window, frame)
                if (cv2.waitKey(1) & 0xFF) in (ord("q"), 27):
                    break
    finally:
        recorder.flush()
        cam.release()
        cv2.destroyAllWindows()

    logger.info("Stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
