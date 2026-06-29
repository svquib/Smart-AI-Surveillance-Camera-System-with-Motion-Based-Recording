"""Activity recognition from pose landmarks.

Turns a stream of `PoseResult`s into a human-readable activity label:
standing, walking, running, falling, or abnormal.

This is a *rule-based* (heuristic) classifier, not a trained model — which is
the right call for a final-year project: it's explainable, needs no labelled
dataset, and runs instantly. Each rule is grounded in simple body geometry:

- Torso angle  : vector from hip-midpoint to shoulder-midpoint vs. vertical.
                 ~0deg = upright; ~90deg = horizontal (lying / collapsed).
- Hip speed    : how fast the hip centre moves between frames, in body-heights
                 per second (so it's scale-invariant to camera distance).
- Drop rate    : sudden downward velocity of the hips -> the moment of a fall.

Decisions are smoothed over a short sliding window so a single noisy frame
can't flip the label. The classifier is deliberately conservative about
"falling"/"abnormal" because those drive emergency alerts in Phase 10.
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Deque, Optional, Tuple

from app.core.logging import get_logger
from app.vision.pose import Landmark, Point, PoseResult

logger = get_logger(__name__)


class Activity(str, Enum):
    NO_PERSON = "no_person"
    STANDING = "standing"
    WALKING = "walking"
    RUNNING = "running"
    FALLING = "falling"
    ABNORMAL = "abnormal"   # e.g. stayed collapsed / lying for a while


@dataclass
class ActivityConfig:
    """Thresholds — calibrate these for your camera height/angle."""

    window_seconds: float = 1.0        # sliding window for smoothing/speed
    walk_speed: float = 0.15           # body-heights/sec to count as walking
    run_speed: float = 0.55            # body-heights/sec to count as running
    fall_angle_deg: float = 55.0       # torso this far from vertical = horizontal
    fall_drop_rate: float = 0.45       # hip downward speed marking a fall event
    abnormal_seconds: float = 4.0      # horizontal this long = abnormal/collapsed
    min_visibility: float = 0.4        # ignore landmarks below this confidence


@dataclass
class ActivityResult:
    activity: Activity
    confidence: float                  # 0..1 rough certainty of the label
    torso_angle: float                 # degrees from vertical
    speed: float                       # body-heights/sec
    metrics: dict = field(default_factory=dict)


@dataclass
class _Sample:
    t: float
    hip: Point
    angle: float
    body_height: float


class ActivityClassifier:
    """Stateful classifier. Feed it one PoseResult per frame.

    >>> clf = ActivityClassifier()
    >>> res = clf.update(pose_result)
    >>> print(res.activity, round(res.confidence, 2))
    """

    def __init__(self, config: Optional[ActivityConfig] = None):
        self.config = config or ActivityConfig()
        self._history: Deque[_Sample] = deque()
        self._horizontal_since: Optional[float] = None

    # ---- geometry helpers ------------------------------------------------
    @staticmethod
    def _torso_angle(hip: Point, shoulder: Point) -> float:
        """Angle (deg) of the hip->shoulder vector away from vertical (upright=0)."""
        dx = shoulder.x - hip.x
        dy = shoulder.y - hip.y  # note: y grows downward
        # Upright => shoulder above hip => dy strongly negative.
        angle = math.degrees(math.atan2(abs(dx), abs(dy) + 1e-6))
        return angle

    @staticmethod
    def _body_height(pose: PoseResult) -> Optional[float]:
        """Vertical extent shoulder->ankle, used to normalise speed."""
        sh = pose.midpoint(Landmark.LEFT_SHOULDER, Landmark.RIGHT_SHOULDER)
        ank = pose.midpoint(Landmark.LEFT_ANKLE, Landmark.RIGHT_ANKLE)
        if sh is None or ank is None:
            return None
        h = abs(ank.y - sh.y)
        return h if h > 0.05 else None

    # ---- main update -----------------------------------------------------
    def update(self, pose: PoseResult, now: Optional[float] = None) -> ActivityResult:
        now = now if now is not None else time.time()

        hip = pose.midpoint(Landmark.LEFT_HIP, Landmark.RIGHT_HIP)
        shoulder = pose.midpoint(Landmark.LEFT_SHOULDER, Landmark.RIGHT_SHOULDER)
        if not pose.present or hip is None or shoulder is None \
                or hip.visibility < self.config.min_visibility:
            self._history.clear()
            self._horizontal_since = None
            return ActivityResult(Activity.NO_PERSON, 0.0, 0.0, 0.0)

        angle = self._torso_angle(hip, shoulder)
        body_h = self._body_height(pose) or 0.4

        # Record sample and trim to the window.
        self._history.append(_Sample(now, hip, angle, body_h))
        cutoff = now - self.config.window_seconds
        while self._history and self._history[0].t < cutoff:
            self._history.popleft()

        speed, drop_rate = self._speeds(body_h)
        activity, conf = self._decide(angle, speed, drop_rate, now)

        return ActivityResult(
            activity=activity,
            confidence=conf,
            torso_angle=round(angle, 1),
            speed=round(speed, 3),
            metrics={"drop_rate": round(drop_rate, 3), "samples": len(self._history)},
        )

    # ---- speed computation ----------------------------------------------
    def _speeds(self, body_h: float) -> Tuple[float, float]:
        """Return (overall hip speed, downward drop rate) in body-heights/sec."""
        if len(self._history) < 2:
            return 0.0, 0.0
        first, last = self._history[0], self._history[-1]
        dt = max(last.t - first.t, 1e-3)
        dx = last.hip.x - first.hip.x
        dy = last.hip.y - first.hip.y
        dist = math.hypot(dx, dy) / body_h
        speed = dist / dt
        drop_rate = (dy / body_h) / dt        # positive = moving downward
        return speed, drop_rate

    # ---- decision rules --------------------------------------------------
    def _decide(self, angle: float, speed: float, drop_rate: float,
                now: float) -> Tuple[Activity, float]:
        cfg = self.config
        horizontal = angle >= cfg.fall_angle_deg

        # Track how long the body has been horizontal (for abnormal/collapsed).
        if horizontal:
            if self._horizontal_since is None:
                self._horizontal_since = now
        else:
            self._horizontal_since = None

        # 1) Fall: torso went horizontal, usually with a fast downward motion.
        if horizontal and drop_rate >= cfg.fall_drop_rate:
            return Activity.FALLING, 0.9
        if horizontal:
            # Already down. Brief => still "falling"; sustained => abnormal.
            down_for = now - (self._horizontal_since or now)
            if down_for >= cfg.abnormal_seconds:
                return Activity.ABNORMAL, 0.8
            return Activity.FALLING, 0.7

        # 2) Upright: distinguish by movement speed.
        if speed >= cfg.run_speed:
            return Activity.RUNNING, 0.8
        if speed >= cfg.walk_speed:
            return Activity.WALKING, 0.75
        return Activity.STANDING, 0.7

    def reset(self) -> None:
        self._history.clear()
        self._horizontal_since = None
