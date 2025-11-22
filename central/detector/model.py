# central/detector/model.py
from typing import List, Tuple, Dict, Any
import numpy as np

BBox = Tuple[int, int, int, int]

class Detection:
    """A simple detection structure."""
    def __init__(self, box: BBox, conf: float) -> None:
        self.box = box
        self.conf = conf

class DetectorStub:
    """Placeholder detector. Replace with real model later."""
    def __init__(self, input_size: int, conf_th: float) -> None:
        self.input_size = input_size
        self.conf_th = conf_th

    def infer(self, image_bgr: np.ndarray) -> List[Detection]:
        """Return bird detections for a full frame or tile.
        This stub returns an empty list.
        """
        return []

def soft_nms(dets: List[Detection], sigma: float, iou_th: float) -> List[Detection]:
    """Soft-NMS placeholder. Replace with a real implementation later."""
    # For now, return as-is to keep the pipeline simple.
    return dets

def iou_aware_score(det: Detection) -> float:
    """Return IoU-aware score placeholder (aligned with VFL/GFLv2 in training)."""
    return det.conf
