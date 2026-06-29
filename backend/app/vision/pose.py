"""Human pose estimation with MediaPipe Pose.

YOLO (Phase 5) tells us a *person* is present; pose estimation tells us how
their body is arranged, which is what activity recognition (walking, running,
falling) is built on. MediaPipe Pose returns 33 body landmarks per frame, each
with a normalised (x, y) position in [0, 1] and a visibility score.

This module is a thin, dependency-isolating wrapper: it loads MediaPipe lazily
and exposes a clean `PoseResult` so the activity classifier never touches the
MediaPipe API directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import List, Optional, Tuple

import numpy as np

from app.core.logging import get_logger

logger = get_logger(__name__)


class Landmark(IntEnum):
    """The MediaPipe Pose landmark indices we actually use."""

    NOSE = 0
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28


@dataclass
class Point:
    x: float            # normalised 0..1 (left->right)
    y: float            # normalised 0..1 (top->bottom)
    visibility: float   # 0..1 confidence the point is visible


@dataclass
class PoseResult:
    """Outcome of running pose estimation on one frame."""

    present: bool                     # was a person/pose detected?
    landmarks: List[Point]            # 33 points (empty if not present)
    bbox: Optional[Tuple[float, float, float, float]] = None  # normalised x,y,w,h

    def point(self, lm: Landmark) -> Optional[Point]:
        if not self.present or lm >= len(self.landmarks):
            return None
        return self.landmarks[lm]

    def midpoint(self, a: Landmark, b: Landmark) -> Optional[Point]:
        pa, pb = self.point(a), self.point(b)
        if pa is None or pb is None:
            return None
        return Point((pa.x + pb.x) / 2, (pa.y + pb.y) / 2,
                     min(pa.visibility, pb.visibility))


@dataclass
class PoseConfig:
    model_complexity: int = 1          # 0=fast, 1=balanced, 2=accurate
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5


class PoseEstimator:
    """MediaPipe Pose wrapper. One instance per camera stream.

    >>> estimator = PoseEstimator()
    >>> result = estimator.process(frame)
    >>> if result.present:
    ...     hips = result.midpoint(Landmark.LEFT_HIP, Landmark.RIGHT_HIP)
    """

    def __init__(self, config: Optional[PoseConfig] = None):
        self.config = config or PoseConfig()
        self._pose = None  # lazy MediaPipe Pose instance

    def load(self) -> None:
        if self._pose is not None:
            return
        import mediapipe as mp  # deferred: heavy import

        logger.info("Loading MediaPipe Pose (complexity=%d)", self.config.model_complexity)
        self._mp = mp
        self._pose = mp.solutions.pose.Pose(
            model_complexity=self.config.model_complexity,
            min_detection_confidence=self.config.min_detection_confidence,
            min_tracking_confidence=self.config.min_tracking_confidence,
        )
        logger.info("MediaPipe Pose ready.")

    def process(self, frame: np.ndarray) -> PoseResult:
        """Run pose estimation on one BGR frame."""
        if self._pose is None:
            self.load()

        import cv2
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        result = self._pose.process(rgb)

        if not result.pose_landmarks:
            return PoseResult(present=False, landmarks=[])

        pts = [
            Point(lm.x, lm.y, lm.visibility)
            for lm in result.pose_landmarks.landmark
        ]

        # Bounding box from visible landmarks (normalised coords).
        xs = [p.x for p in pts if p.visibility > 0.3]
        ys = [p.y for p in pts if p.visibility > 0.3]
        bbox = None
        if xs and ys:
            x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
            bbox = (x0, y0, x1 - x0, y1 - y0)

        return PoseResult(present=True, landmarks=pts, bbox=bbox)

    def close(self) -> None:
        if self._pose is not None:
            self._pose.close()
            self._pose = None
