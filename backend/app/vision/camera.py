"""Camera abstraction over OpenCV's VideoCapture.

This is the single place in the codebase that talks to a physical/virtual
camera. Everything downstream (motion detection, YOLO, recording) consumes
frames from here, so they never need to know whether the source is a laptop
webcam or an RTSP IP camera.

Design goals:
- One class works for BOTH a webcam index ("0") and an RTSP URL.
- Survives transient disconnects (IP cameras drop frames) via auto-reconnect.
- Usable as a context manager so the device is always released.
- Exposes a simple `frames()` generator for the rest of the app to iterate.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterator, Optional

import cv2
import numpy as np

from app.core.logging import get_logger

logger = get_logger(__name__)


def parse_source(source: str | int) -> str | int:
    """Normalise a camera source.

    - "0", "1", ... (or an int)  -> webcam index as int
    - anything else (rtsp://, http://, /path/to/file.mp4) -> kept as string
    """
    if isinstance(source, int):
        return source
    s = str(source).strip()
    if s.isdigit():
        return int(s)
    return s


@dataclass
class CameraConfig:
    """Tunable parameters for a camera connection."""

    source: str | int = 0
    width: Optional[int] = None          # request a capture width (best-effort)
    height: Optional[int] = None         # request a capture height (best-effort)
    fps: Optional[int] = None            # request a capture FPS (best-effort)
    reconnect_attempts: int = 5          # tries before giving up on a dead source
    reconnect_delay: float = 2.0         # seconds between reconnect attempts
    read_timeout_frames: int = 30        # consecutive failed reads -> reconnect


class VideoSource:
    """A resilient wrapper around cv2.VideoCapture.

    Example
    -------
    >>> with VideoSource(CameraConfig(source=0)) as cam:
    ...     for frame in cam.frames():
    ...         do_something(frame)
    """

    def __init__(self, config: CameraConfig):
        self.config = config
        self.source = parse_source(config.source)
        self._cap: Optional[cv2.VideoCapture] = None
        self._failed_reads = 0

    # ---- lifecycle -------------------------------------------------------
    def open(self) -> None:
        """Open the capture device, applying any requested properties."""
        logger.info("Opening camera source: %r", self.source)
        # CAP_FFMPEG is the most reliable backend for RTSP/HTTP streams.
        if isinstance(self.source, str):
            cap = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)
        else:
            cap = cv2.VideoCapture(self.source)

        if self.config.width:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        if self.config.height:
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        if self.config.fps:
            cap.set(cv2.CAP_PROP_FPS, self.config.fps)

        if not cap.isOpened():
            cap.release()
            raise CameraError(f"Could not open camera source: {self.source!r}")

        self._cap = cap
        self._failed_reads = 0
        logger.info(
            "Camera opened (%.0fx%.0f @ %.1f fps)",
            cap.get(cv2.CAP_PROP_FRAME_WIDTH),
            cap.get(cv2.CAP_PROP_FRAME_HEIGHT),
            cap.get(cv2.CAP_PROP_FPS),
        )

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("Camera released: %r", self.source)

    def _reconnect(self) -> bool:
        """Attempt to reopen a dropped source. Returns True on success."""
        self.release()
        for attempt in range(1, self.config.reconnect_attempts + 1):
            logger.warning(
                "Reconnecting to %r (attempt %d/%d)",
                self.source, attempt, self.config.reconnect_attempts,
            )
            try:
                self.open()
                return True
            except CameraError:
                time.sleep(self.config.reconnect_delay)
        logger.error("Giving up on camera source: %r", self.source)
        return False

    # ---- frame access ----------------------------------------------------
    def read(self) -> Optional[np.ndarray]:
        """Read a single frame. Returns None if the source is unavailable.

        Triggers auto-reconnect after `read_timeout_frames` consecutive misses.
        """
        if self._cap is None:
            self.open()

        ok, frame = self._cap.read()  # type: ignore[union-attr]
        if ok and frame is not None:
            self._failed_reads = 0
            return frame

        self._failed_reads += 1
        if self._failed_reads >= self.config.read_timeout_frames:
            if not self._reconnect():
                return None
            self._failed_reads = 0
        return None

    def frames(self) -> Iterator[np.ndarray]:
        """Yield frames indefinitely until the source dies unrecoverably."""
        while True:
            frame = self.read()
            if frame is None:
                # Either a transient miss or a dead source. If the capture is
                # gone entirely, stop the generator.
                if self._cap is None:
                    break
                continue
            yield frame

    @property
    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    # ---- context manager -------------------------------------------------
    def __enter__(self) -> "VideoSource":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


class CameraError(RuntimeError):
    """Raised when a camera source cannot be opened or recovered."""
