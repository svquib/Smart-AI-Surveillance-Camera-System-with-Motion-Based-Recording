"""The full system, end to end, writing to the database.

This is everything from Phases 2-6 stitched together with the Phase 7/8 DB
layer. Per camera it does:

    motion gate -> YOLO (what) + Pose/Activity (doing what) -> record clip
                -> write Event + Alerts to the DB

Run from `backend/` with the venv active and the DB already created
(just boot the API once, or run alembic upgrade head):

    python scripts/run_surveillance.py --camera-id 1
    python scripts/run_surveillance.py --camera-id 1 --device mps
    python scripts/run_surveillance.py --source 0 --no-window     # skip the DB lookup

Then watch them show up live in the API: GET /api/v1/events and /api/v1/alerts.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.camera import Camera  # noqa: E402
from app.services.event_writer import record_event  # noqa: E402
from app.services.recorder import MotionRecorder, RecorderConfig  # noqa: E402
from app.vision.activity import Activity, ActivityClassifier  # noqa: E402
from app.vision.camera import CameraConfig, CameraError, VideoSource  # noqa: E402
from app.vision.detector import DetectorConfig, ObjectDetector  # noqa: E402
from app.vision.motion import MotionConfig, MotionDetector  # noqa: E402
from app.vision.pose import PoseEstimator  # noqa: E402

logger = get_logger("run_surveillance")

# Activities ranked by how much we care — used to pick the "headline" activity
# for an event when several were seen during the clip.
ACTIVITY_PRIORITY = {
    Activity.ABNORMAL.value: 5, Activity.FALLING.value: 4,
    Activity.RUNNING.value: 3, Activity.WALKING.value: 2,
    Activity.STANDING.value: 1, Activity.NO_PERSON.value: 0,
}


def resolve_source(args) -> tuple[str, int | None, str]:
    """Figure out the camera source, id and name from args + DB."""
    if args.source is not None:
        return args.source, args.camera_id, f"camera-{args.camera_id or 'adhoc'}"
    # No explicit source -> look the camera up in the DB.
    db = SessionLocal()
    try:
        cam = db.get(Camera, args.camera_id)
        if not cam:
            raise SystemExit(f"No camera with id {args.camera_id}. "
                             f"Add one via POST /api/v1/cameras or pass --source.")
        return cam.source, cam.id, cam.name
    finally:
        db.close()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Full DB-backed surveillance (Phase 8).")
    p.add_argument("--camera-id", type=int, default=1, help="Camera row id in the DB.")
    p.add_argument("--source", default=None,
                   help="Override the camera source (skips the DB lookup).")
    p.add_argument("--threshold", type=int, default=settings.MOTION_THRESHOLD)
    p.add_argument("--conf", type=float, default=0.35)
    p.add_argument("--device", default=None, help='"cpu", "mps", "cuda:0".')
    p.add_argument("--fps", type=int, default=20)
    p.add_argument("--detect-every", type=int, default=3)
    p.add_argument("--no-window", action="store_true")
    return p.parse_args()


def main() -> int:
    configure_logging()
    args = parse_args()
    source, camera_id, camera_name = resolve_source(args)
    logger.info("Camera: %s (id=%s) source=%r", camera_name, camera_id, source)

    cam = VideoSource(CameraConfig(source=source))
    motion = MotionDetector(MotionConfig(motion_threshold=args.threshold))
    detector = ObjectDetector(DetectorConfig(conf_threshold=args.conf, device=args.device))
    pose = PoseEstimator()
    activity_clf = ActivityClassifier()
    recorder = MotionRecorder(RecorderConfig(fps=args.fps, camera_name=camera_name))

    logger.info("Loading models...")
    detector.load()
    pose.load()

    try:
        cam.open()
    except CameraError as exc:
        logger.error("%s", exc)
        return 1

    # Per-event accumulators (reset after each saved clip).
    obj_counts: Counter = Counter()
    best_conf: dict[str, float] = {}
    act_counts: Counter = Counter()

    frame_idx = 0
    last_dets = []
    window = "Phase 8 - Full Surveillance (q to quit)"
    logger.info("Running. Trigger some motion; events will appear in the DB.")

    try:
        while True:
            frame = cam.read()
            if frame is None:
                if not cam.is_open:
                    break
                continue
            frame_idx += 1

            m = motion.process(frame)

            if m.motion:
                # YOLO only every Nth frame to save compute.
                if frame_idx % args.detect_every == 0:
                    last_dets = detector.detect(frame)
                    for d in last_dets:
                        obj_counts[d.category] += 1
                        best_conf[d.category] = max(best_conf.get(d.category, 0), d.confidence)
                # Pose/activity every motion frame (it's cheap and temporal).
                act = activity_clf.update(pose.process(frame))
                act_counts[act.activity.value] += 1

            meta = recorder.feed(frame, motion=m.motion, score=m.score)
            if meta:
                _persist(camera_id, camera_name, meta, obj_counts, best_conf, act_counts)
                obj_counts.clear(); best_conf.clear(); act_counts.clear()
                last_dets = []

            if not args.no_window:
                _draw(frame, last_dets, recorder.is_recording, m.score)
                cv2.imshow(window, frame)
                if (cv2.waitKey(1) & 0xFF) in (ord("q"), 27):
                    break
    finally:
        meta = recorder.flush()
        if meta:
            _persist(camera_id, camera_name, meta, obj_counts, best_conf, act_counts)
        pose.close()
        cam.release()
        cv2.destroyAllWindows()

    logger.info("Stopped.")
    return 0


def _persist(camera_id, camera_name, meta, obj_counts, best_conf, act_counts):
    """Pick the headline object/activity for the clip and write it to the DB."""
    top_object = obj_counts.most_common(1)[0][0] if obj_counts else None
    confidence = best_conf.get(top_object) if top_object else None
    # Headline activity = the one we care about most that was actually seen.
    activity = "no_person"
    if act_counts:
        activity = max(act_counts, key=lambda a: (ACTIVITY_PRIORITY.get(a, 0), act_counts[a]))

    db = SessionLocal()
    try:
        record_event(
            db,
            camera_id=camera_id,
            camera_name=camera_name,
            object_counts=dict(obj_counts),
            top_object=top_object,
            confidence=round(confidence, 3) if confidence else None,
            activity=activity,
            video_path=meta.video_path,
            snapshot_path=meta.snapshot_path,
            when=datetime.utcnow(),
        )
    finally:
        db.close()


def _draw(frame, dets, recording, score):
    colors = {"person": (0, 255, 0), "cat": (0, 255, 255), "dog": (0, 200, 255),
              "vehicle": (255, 128, 0), "other": (180, 180, 180)}
    for d in dets:
        x, y, w, h = d.box
        c = colors.get(d.category, (180, 180, 180))
        cv2.rectangle(frame, (x, y), (x + w, y + h), c, 2)
        cv2.putText(frame, f"{d.label} {d.confidence:.2f}", (x, y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, c, 2)
    label = "REC ●" if recording else "IDLE"
    col = (0, 0, 255) if recording else (0, 200, 0)
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 36), (30, 30, 30), -1)
    cv2.putText(frame, f"{label}  score={score}", (12, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)


if __name__ == "__main__":
    raise SystemExit(main())
