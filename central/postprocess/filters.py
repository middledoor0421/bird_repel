# central/postprocess/filters.py
from typing import List
from ..detector.model import Detection

def filter_by_min_box(dets: List[Detection], min_size_px: int) -> List[Detection]:
    """Drop boxes smaller than min_size in either side."""
    out: List[Detection] = []
    for d in dets:
        _, _, w, h = d.box
        if int(w) >= int(min_size_px) and int(h) >= int(min_size_px):
            out.append(d)
    return out
