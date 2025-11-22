# central/tracker/types.py
from typing import Tuple
from dataclasses import dataclass

BBox = Tuple[int, int, int, int]

@dataclass
class Track:
    """Track representation used by the event builder."""
    track_id: str
    box: BBox
    conf: float
