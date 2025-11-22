# central/sahi_runner/runner.py
from typing import Tuple

class SAHIPolicy:
    """Decide whether to promote a frame/tile to SAHI."""
    def __init__(self, small_area_ratio: float, conf_low: float) -> None:
        self.small_area_ratio = small_area_ratio
        self.conf_low = conf_low

    def should_promote(self, box_area_px: int, image_area_px: int, conf: float) -> bool:
        """Return True if the object is small or has low confidence."""
        small = (float(box_area_px) / float(image_area_px)) < self.small_area_ratio
        low = conf < self.conf_low
        return bool(small or low)
