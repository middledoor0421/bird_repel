from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from thesis3.core import BBox
from thesis3.dataclass_compat import dataclass


@dataclass(slots=True)
class LoadedImage:
    path: str
    width: int
    height: int
    mode: str
    array: np.ndarray


def load_rgb_image(path: str | Path) -> LoadedImage:
    image_path = Path(path)
    with Image.open(image_path) as image:
        rgb_image = image.convert("RGB")
        array = np.asarray(rgb_image)
        return LoadedImage(
            path=str(image_path),
            width=rgb_image.width,
            height=rgb_image.height,
            mode=rgb_image.mode,
            array=array,
        )


def crop_array(array: np.ndarray, bbox: BBox | None) -> np.ndarray:
    if bbox is None:
        return array
    height, width = array.shape[:2]
    x1 = max(0, min(width, int(round(bbox.x1))))
    y1 = max(0, min(height, int(round(bbox.y1))))
    x2 = max(0, min(width, int(round(bbox.x2))))
    y2 = max(0, min(height, int(round(bbox.y2))))
    if x2 <= x1 or y2 <= y1:
        return array[0:0, 0:0]
    return array[y1:y2, x1:x2]


def bbox_iou(lhs: BBox, rhs: BBox) -> float:
    inter_x1 = max(lhs.x1, rhs.x1)
    inter_y1 = max(lhs.y1, rhs.y1)
    inter_x2 = min(lhs.x2, rhs.x2)
    inter_y2 = min(lhs.y2, rhs.y2)
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    intersection = inter_w * inter_h
    if intersection <= 0.0:
        return 0.0
    union = lhs.area + rhs.area - intersection
    if union <= 0.0:
        return 0.0
    return intersection / union


def normalized_grayscale_mean(array: np.ndarray) -> float:
    if array.size == 0:
        return 0.0
    grayscale = array.mean(axis=2) if array.ndim == 3 else array
    return float(np.asarray(grayscale, dtype=np.float32).mean() / 255.0)


def normalized_grayscale_std(array: np.ndarray) -> float:
    if array.size == 0:
        return 0.0
    grayscale = array.mean(axis=2) if array.ndim == 3 else array
    return float(min(1.0, np.asarray(grayscale, dtype=np.float32).std() / 64.0))


def centered_bbox(width: int, height: int, width_ratio: float, height_ratio: float) -> BBox:
    box_width = max(1.0, width * width_ratio)
    box_height = max(1.0, height * height_ratio)
    x1 = (width - box_width) / 2.0
    y1 = (height - box_height) / 2.0
    return BBox(x1=x1, y1=y1, x2=x1 + box_width, y2=y1 + box_height)
