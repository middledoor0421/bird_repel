# central/sahi_runner/runner.py
# Python 3.9 compatible. Comments in English.
from typing import List, Tuple
import numpy as np
from ..detector.model import Detection
from ..postprocess.nms import soft_nms_gaussian

BBox = Tuple[int, int, int, int]

class SAHIExecutor:
    """Run detector on selected tiles and merge results to the global space."""
    def __init__(self, tile_size: int, overlap: float, merge_iou: float, sigma: float = 0.5, max_tiles: int = 8) -> None:
        self.tile_size = int(tile_size)
        self.overlap = float(overlap)
        self.merge_iou = float(merge_iou)
        self.sigma = float(sigma)
        self.max_tiles = int(max_tiles)

    def _intersects(self, a: BBox, b: BBox) -> bool:
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)

    def select_tiles(self, image_shape: Tuple[int, int], triggers: List[BBox]) -> List[BBox]:
        """Generate overlapping tiles, keep those intersecting trigger boxes (limited by max_tiles)."""
        h, w = image_shape
        ts = self.tile_size
        ov = max(0.0, min(self.overlap, 0.9))
        sx = max(1, int(ts * (1.0 - ov)))
        sy = sx
        xs = list(range(0, max(1, w - ts + 1), sx)) or [0]
        ys = list(range(0, max(1, h - ts + 1), sy)) or [0]
        all_tiles: List[BBox] = []
        for y in ys:
            for x in xs:
                all_tiles.append((x, y, min(ts, w - x), min(ts, h - y)))

        if len(triggers) == 0:
            # if no trigger given, select first tiles up to limit
            return all_tiles[: self.max_tiles]

        selected: List[BBox] = []
        for t in all_tiles:
            if any(self._intersects(t, g) for g in triggers):
                selected.append(t)
                if len(selected) >= self.max_tiles:
                    break
        return selected

    def run(self, frame_bgr, detector, tiles: List[BBox]) -> List[Detection]:
        """Run detector on tiles and merge with Soft-NMS."""
        dets_all: List[Detection] = []
        for x, y, w, h in tiles:
            roi = frame_bgr[y : y + h, x : x + w]
            sub = detector.infer(roi)  # local coords
            # offset to global coords
            for d in sub:
                gx, gy, gw, gh = d.box
                d.box = (int(gx + x), int(gy + y), int(gw), int(gh))
                dets_all.append(d)
        # merge: Gaussian Soft-NMS in global space
        merged = soft_nms_gaussian(dets_all, sigma=self.sigma, iou_th=self.merge_iou, score_th=0.001)
        return merged
