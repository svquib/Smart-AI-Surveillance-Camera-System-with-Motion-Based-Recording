"""Motion detection.

Purpose: cheaply decide whether *anything is moving* in the frame, so the
expensive AI stages (YOLO, MediaPipe) only run when they have to. On an idle
scene this stage keeps CPU/GPU usage near zero.

Two classic, complementary techniques are implemented behind one interface:

1. Background subtraction (MOG2)  [default]
   OpenCV learns a statistical model of the static background and flags pixels
   that deviate. Robust to gradual lighting changes; great for fixed cameras.

2. Frame differencing (absdiff)
   Compare the current frame to the previous one. Simpler and faster, but only
   sees a pixel while it is actually changing. Good fallback / teaching example.

Both return the same `MotionResult`, so callers (Phase 4 recorder, Phase 5
detector) don't care which method is active.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2
import numpy as np

from app.core.logging import get_logger

logger = get_logger(__name__)

BBox = Tuple[int, int, int, int]  # (x, y, w, h)


@dataclass
class MotionConfig:
    """Tunable parameters for motion detection."""

    method: str = "mog2"          # "mog2" (background subtraction) or "diff"
    min_area: int = 800           # ignore contours smaller than this (px^2) -> noise
    motion_threshold: int = 5000  # total changed area (px^2) to call it "motion"
    blur_kernel: int = 21         # Gaussian blur to suppress sensor noise (odd number)
    diff_threshold: int = 25      # pixel-intensity delta to count as "changed"
    dilate_iterations: int = 2    # grow blobs so nearby motion merges
    # MOG2-specific
    history: int = 500            # frames used to build the background model
    var_threshold: int = 16       # sensitivity; lower = more sensitive
    detect_shadows: bool = True   # mark shadows (value 127) so we can drop them
    warmup_frames: int = 15       # frames to let the model settle before reporting


@dataclass
class MotionResult:
    """Outcome of analysing a single frame."""

    motion: bool                       # did motion exceed the threshold?
    score: int                         # total moving area in pixels
    boxes: List[BBox] = field(default_factory=list)  # bounding boxes of moving blobs
    mask: Optional[np.ndarray] = None  # binary foreground mask (for debugging/preview)


class MotionDetector:
    """Stateful motion detector. Create one per camera stream.

    Example
    -------
    >>> detector = MotionDetector(MotionConfig())
    >>> result = detector.process(frame)
    >>> if result.motion:
    ...     run_ai(frame)
    """

    def __init__(self, config: Optional[MotionConfig] = None):
        self.config = config or MotionConfig()
        self._prev_gray: Optional[np.ndarray] = None
        self._frames_seen = 0

        if self.config.method == "mog2":
            self._bg = cv2.createBackgroundSubtractorMOG2(
                history=self.config.history,
                varThreshold=self.config.var_threshold,
                detectShadows=self.config.detect_shadows,
            )
        elif self.config.method == "diff":
            self._bg = None
        else:
            raise ValueError(f"Unknown motion method: {self.config.method!r}")

    # ---- helpers ---------------------------------------------------------
    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        """Grayscale + blur: removes colour and high-frequency sensor noise."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        k = self.config.blur_kernel | 1  # force odd
        return cv2.GaussianBlur(gray, (k, k), 0)

    def _foreground_mask(self, frame: np.ndarray, gray: np.ndarray) -> np.ndarray:
        """Produce a binary mask of moving pixels using the chosen method."""
        if self.config.method == "mog2":
            mask = self._bg.apply(frame)
            # MOG2 marks shadows as 127; keep only hard foreground (255).
            _, mask = cv2.threshold(mask, 200, 255, cv2.THRESH_BINARY)
        else:  # frame differencing
            if self._prev_gray is None:
                self._prev_gray = gray
                return np.zeros_like(gray)
            delta = cv2.absdiff(self._prev_gray, gray)
            _, mask = cv2.threshold(
                delta, self.config.diff_threshold, 255, cv2.THRESH_BINARY
            )
            self._prev_gray = gray

        # Close gaps and merge nearby blobs.
        mask = cv2.dilate(mask, None, iterations=self.config.dilate_iterations)
        return mask

    # ---- public API ------------------------------------------------------
    def process(self, frame: np.ndarray) -> MotionResult:
        """Analyse one BGR frame and report whether meaningful motion occurred."""
        self._frames_seen += 1
        gray = self._preprocess(frame)
        mask = self._foreground_mask(frame, gray)

        # During warmup the background model is still learning -> suppress output.
        if self._frames_seen <= self.config.warmup_frames:
            return MotionResult(motion=False, score=0, boxes=[], mask=mask)

        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        boxes: List[BBox] = []
        total_area = 0
        for c in contours:
            area = cv2.contourArea(c)
            if area < self.config.min_area:
                continue
            total_area += int(area)
            boxes.append(tuple(cv2.boundingRect(c)))  # type: ignore[arg-type]

        motion = total_area >= self.config.motion_threshold
        return MotionResult(motion=motion, score=total_area, boxes=boxes, mask=mask)

    def reset(self) -> None:
        """Forget learned state (e.g. after the camera is repositioned)."""
        self._prev_gray = None
        self._frames_seen = 0
        if self.config.method == "mog2":
            self._bg = cv2.createBackgroundSubtractorMOG2(
                history=self.config.history,
                varThreshold=self.config.var_threshold,
                detectShadows=self.config.detect_shadows,
            )
        logger.info("MotionDetector reset")
