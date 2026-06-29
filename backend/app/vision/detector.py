"""Object detection with YOLOv11 (Ultralytics).

This stage answers "what is in the frame?" and only runs when motion has
already been detected (see scripts/detect_on_motion.py), so the GPU/CPU stays
idle on an empty scene.

The Ultralytics model is loaded lazily on first use. The first run will
auto-download the weights file (`yolo11n.pt`, the small/fast variant) into the
working directory — no manual download needed.

The raw model speaks COCO's 80 classes. The project only cares about a handful
of high-level categories (person / cat / dog / vehicle / other), so we map the
fine-grained COCO label into a `category` while still keeping the exact label.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np

from app.core.logging import get_logger

logger = get_logger(__name__)

BBox = Tuple[int, int, int, int]  # (x, y, w, h)

# COCO labels that the project groups under "vehicle".
VEHICLE_LABELS = {"bicycle", "car", "motorcycle", "bus", "train", "truck", "boat"}


def to_category(label: str) -> str:
    """Collapse a COCO label into a project category."""
    if label == "person":
        return "person"
    if label == "cat":
        return "cat"
    if label == "dog":
        return "dog"
    if label in VEHICLE_LABELS:
        return "vehicle"
    return "other"


@dataclass
class DetectorConfig:
    """Tunable parameters for the detector."""

    model_path: str = "yolo11n.pt"      # n=nano (fast). Try yolo11s/m for accuracy.
    conf_threshold: float = 0.35        # drop detections below this confidence
    iou_threshold: float = 0.45         # NMS overlap threshold
    imgsz: int = 640                    # inference resolution
    device: Optional[str] = None        # None=auto; "cpu", "mps" (Apple), "cuda:0"
    # Restrict to these COCO labels (None = detect everything the model knows).
    classes_of_interest: Optional[Sequence[str]] = None


@dataclass
class Detection:
    """One detected object."""

    label: str           # exact COCO label, e.g. "car"
    category: str         # project category, e.g. "vehicle"
    confidence: float     # 0..1
    box: BBox             # (x, y, w, h) in pixels
    class_id: int


class ObjectDetector:
    """YOLOv11 wrapper. Construct once, reuse for every frame.

    >>> detector = ObjectDetector(DetectorConfig())
    >>> detections = detector.detect(frame)
    >>> for d in detections:
    ...     print(d.category, d.label, round(d.confidence, 2))
    """

    def __init__(self, config: Optional[DetectorConfig] = None):
        self.config = config or DetectorConfig()
        self._model = None              # lazy-loaded Ultralytics YOLO
        self._names: dict[int, str] = {}
        self._allowed_ids: Optional[List[int]] = None

    # ---- model loading ---------------------------------------------------
    def load(self) -> None:
        """Load the YOLO model. Safe to call repeatedly (no-op after first)."""
        if self._model is not None:
            return
        # Imported here so the rest of the app doesn't pull in torch/ultralytics
        # unless object detection is actually used.
        from ultralytics import YOLO

        logger.info("Loading YOLO model: %s", self.config.model_path)
        self._model = YOLO(self.config.model_path)
        self._names = self._model.names  # {id: label}

        if self.config.classes_of_interest:
            wanted = set(self.config.classes_of_interest)
            self._allowed_ids = [
                i for i, name in self._names.items() if name in wanted
            ]
            logger.info("Restricting detection to: %s", sorted(wanted))
        logger.info("YOLO model ready (%d classes).", len(self._names))

    # ---- inference -------------------------------------------------------
    def detect(self, frame: np.ndarray) -> List[Detection]:
        """Run detection on one BGR frame and return filtered detections."""
        if self._model is None:
            self.load()

        results = self._model.predict(  # type: ignore[union-attr]
            source=frame,
            conf=self.config.conf_threshold,
            iou=self.config.iou_threshold,
            imgsz=self.config.imgsz,
            device=self.config.device,
            classes=self._allowed_ids,
            verbose=False,
        )

        detections: List[Detection] = []
        if not results:
            return detections

        boxes = results[0].boxes
        if boxes is None:
            return detections

        for b in boxes:
            cls_id = int(b.cls[0])
            conf = float(b.conf[0])
            x1, y1, x2, y2 = (int(v) for v in b.xyxy[0])
            label = self._names.get(cls_id, str(cls_id))
            detections.append(
                Detection(
                    label=label,
                    category=to_category(label),
                    confidence=conf,
                    box=(x1, y1, x2 - x1, y2 - y1),
                    class_id=cls_id,
                )
            )
        return detections

    def best(self, detections: List[Detection]) -> Optional[Detection]:
        """Return the highest-confidence detection (handy for a dashboard)."""
        return max(detections, key=lambda d: d.confidence, default=None)
