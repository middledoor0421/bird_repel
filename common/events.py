# common/events.py
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

class BirdTarget(BaseModel):
    """Event emitted by Central → consumed by Laser."""
    track_id: str
    t: int                           # epoch(ms)
    cam_id: str
    bearing: float                   # degrees
    box: List[float]                 # [x, y, w, h] in px
    conf: float                      # IoU-aware confidence
    size_px: int
    need_recheck: bool
    meta: Optional[Dict[str, Any]] = None
