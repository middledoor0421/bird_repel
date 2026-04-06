from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class BirdRepelLikeDetection:
    box: tuple[int, int, int, int]
    conf: float


class BirdRepelLikeDetector:
    def __init__(self, min_confidence: float = 0.4, target_class_name: str = "target") -> None:
        self.min_confidence = min_confidence
        self.target_class_name = target_class_name

    def infer(self, frame_like: Any):
        if hasattr(frame_like, "metadata"):
            detections = frame_like.metadata.get("detections", [])
            result = []
            for raw in detections:
                score = float(raw.get("score", 0.0))
                if score < self.min_confidence:
                    continue
                if str(raw.get("class_name", "")) != self.target_class_name:
                    continue
                x1, y1, x2, y2 = [int(value) for value in raw["bbox"]]
                result.append(BirdRepelLikeDetection(box=(x1, y1, x2 - x1, y2 - y1), conf=score))
            return result

        if isinstance(frame_like, np.ndarray):
            height, width = frame_like.shape[:2]
            return [BirdRepelLikeDetection(box=(width // 4, height // 4, width // 3, height // 3), conf=0.8)]

        return []


class BirdSahiLikeYoloDetector:
    def __init__(self, min_confidence: float = 0.4, target_class_name: str = "target") -> None:
        self.min_confidence = min_confidence
        self.target_class_name = target_class_name

    def predict(self, frame_like: Any, conf_thres: float | None = None, img_size: int | None = None):
        threshold = self.min_confidence if conf_thres is None else float(conf_thres)
        if hasattr(frame_like, "metadata"):
            boxes = []
            scores = []
            labels = []
            for raw in frame_like.metadata.get("detections", []):
                score = float(raw.get("score", 0.0))
                if score < threshold:
                    continue
                boxes.append(raw["bbox"])
                scores.append(score)
                labels.append(0 if str(raw.get("class_name", "")) == self.target_class_name else 1)
            return (
                np.asarray(boxes, dtype=np.float32).reshape((-1, 4)) if boxes else np.zeros((0, 4), dtype=np.float32),
                np.asarray(scores, dtype=np.float32),
                np.asarray(labels, dtype=np.int64),
            )

        if isinstance(frame_like, np.ndarray):
            height, width = frame_like.shape[:2]
            return (
                np.asarray([[width * 0.2, height * 0.2, width * 0.55, height * 0.55]], dtype=np.float32),
                np.asarray([0.82], dtype=np.float32),
                np.asarray([0], dtype=np.int64),
            )

        return (
            np.zeros((0, 4), dtype=np.float32),
            np.zeros((0,), dtype=np.float32),
            np.zeros((0,), dtype=np.int64),
        )
