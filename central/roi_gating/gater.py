# central/roi_gating/gater.py
from typing import List, Tuple, Optional
import cv2
import numpy as np

BBox = Tuple[int, int, int, int]  # x, y, w, h

class ROIGater:
    """Stage0: motion-based ROI gating + tile proposal."""
    def __init__(self, diff_th: int, min_area: int,
                 tile_size: int, overlap: float) -> None:
        self.diff_th = diff_th
        self.min_area = min_area
        self.tile_size = tile_size
        self.overlap = overlap
        self.prev_gray: Optional[np.ndarray] = None

    def motion_mask(self, frame_bgr: np.ndarray) -> np.ndarray:
        """Return binary motion mask using frame differencing."""
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        if self.prev_gray is None:
            self.prev_gray = gray
            return np.zeros_like(gray)
        diff = cv2.absdiff(gray, self.prev_gray)
        self.prev_gray = gray
        mask = (diff > self.diff_th).astype(np.uint8) * 255
        mask = cv2.medianBlur(mask, 3)
        return mask

    def propose_tiles(self, shape: Tuple[int, int]) -> List[BBox]:
        """Generate overlapping tiles over the image."""
        h, w = shape
        ts = self.tile_size
        ov = max(0.0, min(self.overlap, 0.9))
        sx = max(1, int(ts * (1.0 - ov)))
        sy = sx
        xs = list(range(0, max(1, w - ts + 1), sx)) or [0]
        ys = list(range(0, max(1, h - ts + 1), sy)) or [0]
        tiles: List[BBox] = []
        for y in ys:
            for x in xs:
                tiles.append((x, y, min(ts, w - x), min(ts, h - y)))
        return tiles

    def moving_tiles(self, frame_bgr: np.ndarray) -> List[BBox]:
        """Return subset of tiles intersecting with motion mask."""
        mask = self.motion_mask(frame_bgr)
        h, w = mask.shape
        tiles = self.propose_tiles((h, w))
        selected: List[BBox] = []
        for x, y, tw, th in tiles:
            roi = mask[y:y+th, x:x+tw]
            if int(cv2.countNonZero(roi)) >= self.min_area:
                selected.append((x, y, tw, th))
        return selected
