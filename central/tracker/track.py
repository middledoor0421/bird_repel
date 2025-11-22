# central/tracker/track.py
from typing import List, Tuple
from .types import Track
from ..detector.model import Detection, BBox

class SimpleTracker:
    """Tiny tracker to attach incremental IDs (for scaffolding only)."""
    def __init__(self) -> None:
        self._next_id = 1

    def update(self, dets: List[Detection]) -> List[Track]:
        """Attach incremental IDs to detections (no temporal logic)."""
        tracks: List[Track] = []
        for d in dets:
            tid = f"T{self._next_id}"
            self._next_id += 1
            tracks.append(Track(track_id=tid, box=d.box, conf=d.conf))
        return tracks
