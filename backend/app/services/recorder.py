"""Motion-triggered clip recorder.

Records video *only* while something is happening, but with two refinements
that make the footage actually useful:

1. Pre-buffer (pre-roll)
   We keep the last few seconds of frames in a ring buffer at all times. When
   motion fires, those buffered frames are written first — so the clip shows
   the moments *leading up to* the event, not just the aftermath.

2. Post-motion cooldown (hangover)
   We keep recording for a few seconds after motion stops, so a person who
   briefly pauses doesn't get chopped into many tiny clips.

State machine:

        IDLE ──motion──► RECORDING ──no motion for `post_motion_seconds`──► IDLE
                              │
                              └── motion keeps resetting the cooldown timer

Each finished clip produces a `RecordingMetadata` object and a JSON sidecar
file. Phase 8 will persist that metadata to the database; for now it's written
next to the video so nothing is lost.
"""

from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Deque, List, Optional

import cv2
import numpy as np

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RecorderConfig:
    """Tunable parameters for the recorder."""

    output_dir: Path = settings.RECORDINGS_DIR
    snapshot_dir: Path = settings.SNAPSHOTS_DIR
    fps: int = 20                       # frame rate written into the clip
    pre_buffer_seconds: int = settings.PRE_BUFFER_SECONDS
    post_motion_seconds: float = 3.0    # keep recording this long after motion ends
    max_clip_seconds: int = 120         # safety cap so a clip can't grow forever
    fourcc: str = "mp4v"                # codec; "mp4v" -> .mp4, widely compatible
    extension: str = "mp4"
    camera_name: str = "camera-1"       # used in filenames + metadata


@dataclass
class RecordingMetadata:
    """Everything we know about one saved clip (ready to store in the DB)."""

    camera_name: str
    video_path: str
    snapshot_path: Optional[str]
    started_at: str           # ISO 8601 UTC
    ended_at: str             # ISO 8601 UTC
    duration_seconds: float
    frame_count: int
    fps: int
    trigger_score: int        # motion score that started the clip
    width: int
    height: int


class MotionRecorder:
    """Drives the IDLE/RECORDING state machine. Feed it one frame at a time.

    Usage (see scripts/record_on_motion.py for the full loop):

    >>> recorder = MotionRecorder(RecorderConfig())
    >>> meta = recorder.feed(frame, motion=result.motion, score=result.score)
    >>> if meta:          # a clip just finished
    ...     save_to_db(meta)
    """

    def __init__(self, config: Optional[RecorderConfig] = None):
        self.config = config or RecorderConfig()
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        self.config.snapshot_dir.mkdir(parents=True, exist_ok=True)

        # Ring buffer holds the most recent N frames for the pre-roll.
        buffer_len = max(1, self.config.pre_buffer_seconds * self.config.fps)
        self._prebuffer: Deque[np.ndarray] = deque(maxlen=buffer_len)

        self._writer: Optional[cv2.VideoWriter] = None
        self._recording = False
        self._last_motion_ts = 0.0
        self._clip_start_ts = 0.0
        self._frame_count = 0
        self._frame_size: Optional[tuple[int, int]] = None
        self._video_path: Optional[Path] = None
        self._snapshot_path: Optional[Path] = None
        self._trigger_score = 0

    # ---- public API ------------------------------------------------------
    @property
    def is_recording(self) -> bool:
        return self._recording

    def feed(
        self, frame: np.ndarray, motion: bool, score: int = 0
    ) -> Optional[RecordingMetadata]:
        """Process one frame. Returns metadata only when a clip is finalised."""
        now = time.time()
        h, w = frame.shape[:2]
        self._frame_size = (w, h)

        # Always keep the most recent frames available for pre-roll.
        self._prebuffer.append(frame.copy())

        if not self._recording:
            if motion:
                self._start_clip(frame, score, now)
            return None

        # --- currently RECORDING ---
        self._writer.write(frame)  # type: ignore[union-attr]
        self._frame_count += 1

        if motion:
            self._last_motion_ts = now

        cooldown_over = (now - self._last_motion_ts) >= self.config.post_motion_seconds
        too_long = (now - self._clip_start_ts) >= self.config.max_clip_seconds
        if cooldown_over or too_long:
            return self._finalize_clip(now)
        return None

    def flush(self) -> Optional[RecordingMetadata]:
        """Finalise any in-progress clip (call on shutdown)."""
        if self._recording:
            return self._finalize_clip(time.time())
        return None

    # ---- internals -------------------------------------------------------
    def _start_clip(self, frame: np.ndarray, score: int, now: float) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        w, h = self._frame_size  # type: ignore[misc]
        name = f"{self.config.camera_name}_{ts}"
        self._video_path = self.config.output_dir / f"{name}.{self.config.extension}"
        self._snapshot_path = self.config.snapshot_dir / f"{name}.jpg"

        fourcc = cv2.VideoWriter_fourcc(*self.config.fourcc)
        self._writer = cv2.VideoWriter(
            str(self._video_path), fourcc, self.config.fps, (w, h)
        )
        if not self._writer.isOpened():
            logger.error("Failed to open VideoWriter for %s", self._video_path)
            self._writer = None
            return

        # Snapshot at the trigger moment (used later for SOS alerts).
        cv2.imwrite(str(self._snapshot_path), frame)

        # Write the pre-roll first so the clip includes the run-up to motion.
        for buffered in list(self._prebuffer):
            self._writer.write(buffered)

        self._recording = True
        self._frame_count = len(self._prebuffer)
        self._clip_start_ts = now
        self._last_motion_ts = now
        self._trigger_score = score
        logger.info(
            "Recording started: %s (pre-roll=%d frames, score=%d)",
            self._video_path.name, len(self._prebuffer), score,
        )

    def _finalize_clip(self, now: float) -> RecordingMetadata:
        assert self._writer is not None and self._video_path is not None
        self._writer.release()
        self._recording = False

        duration = round(self._frame_count / self.config.fps, 2)
        w, h = self._frame_size  # type: ignore[misc]
        started = datetime.fromtimestamp(self._clip_start_ts, tz=timezone.utc)
        ended = datetime.fromtimestamp(now, tz=timezone.utc)

        meta = RecordingMetadata(
            camera_name=self.config.camera_name,
            video_path=str(self._video_path),
            snapshot_path=str(self._snapshot_path) if self._snapshot_path else None,
            started_at=started.isoformat(),
            ended_at=ended.isoformat(),
            duration_seconds=duration,
            frame_count=self._frame_count,
            fps=self.config.fps,
            trigger_score=self._trigger_score,
            width=w,
            height=h,
        )

        # Write a JSON sidecar so metadata survives until the DB exists (Phase 8).
        sidecar = self._video_path.with_suffix(".json")
        sidecar.write_text(json.dumps(asdict(meta), indent=2))

        logger.info(
            "Recording saved: %s (%.1fs, %d frames)",
            self._video_path.name, duration, self._frame_count,
        )
        self._writer = None
        return meta
