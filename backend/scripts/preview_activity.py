"""Phase 6 test tool — live pose skeleton + activity label.

Run from `backend/` with your venv active:

    python scripts/preview_activity.py
    python scripts/preview_activity.py --source "rtsp://user:pass@host:554/stream"

You'll see the MediaPipe skeleton drawn on your body and a banner showing the
classified activity, torso angle, and speed.

Try it out:
    - Stand still           -> STANDING
    - Walk across the frame -> WALKING
    - Move quickly          -> RUNNING
    - Lie down / collapse    -> FALLING, then ABNORMAL after a few seconds

Controls:  q / ESC -> quit
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.vision.camera import CameraConfig, CameraError, VideoSource  # noqa: E402
from app.vision.pose import PoseEstimator  # noqa: E402
from app.vision.activity import Activity, ActivityClassifier  # noqa: E402

ACTIVITY_COLORS = {
    Activity.NO_PERSON: (150, 150, 150),
    Activity.STANDING: (0, 200, 0),
    Activity.WALKING: (0, 200, 200),
    Activity.RUNNING: (0, 165, 255),
    Activity.FALLING: (0, 0, 255),
    Activity.ABNORMAL: (0, 0, 255),
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Live activity recognition (Phase 6 test).")
    p.add_argument("--source", default=settings.DEFAULT_CAMERA_SOURCE)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    cam = VideoSource(CameraConfig(source=args.source))
    estimator = PoseEstimator()
    classifier = ActivityClassifier()

    # MediaPipe's drawing utilities for the skeleton overlay.
    import mediapipe as mp
    estimator.load()
    mp_draw = mp.solutions.drawing_utils
    mp_pose = mp.solutions.pose

    try:
        cam.open()
    except CameraError as exc:
        print(f"ERROR: {exc}")
        return 1

    window = "Phase 6 - Activity Recognition (q to quit)"

    try:
        while True:
            frame = cam.read()
            if frame is None:
                if not cam.is_open:
                    break
                continue

            # Run pose, then re-run raw mediapipe once for drawing convenience.
            result = estimator.process(frame)
            act = classifier.update(result)

            # Draw skeleton if present.
            if result.present:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                raw = estimator._pose.process(rgb)  # reuse loaded model
                if raw.pose_landmarks:
                    mp_draw.draw_landmarks(
                        frame, raw.pose_landmarks, mp_pose.POSE_CONNECTIONS
                    )

            color = ACTIVITY_COLORS.get(act.activity, (200, 200, 200))
            cv2.rectangle(frame, (0, 0), (frame.shape[1], 40), (30, 30, 30), -1)
            cv2.putText(
                frame,
                f"{act.activity.value.upper()}  angle={act.torso_angle:.0f}deg  "
                f"speed={act.speed:.2f}  conf={act.confidence:.2f}",
                (12, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2,
            )
            if act.activity in (Activity.FALLING, Activity.ABNORMAL):
                cv2.rectangle(frame, (0, 0),
                              (frame.shape[1] - 1, frame.shape[0] - 1), (0, 0, 255), 6)

            cv2.imshow(window, frame)
            if (cv2.waitKey(1) & 0xFF) in (ord("q"), 27):
                break
    finally:
        estimator.close()
        cam.release()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
