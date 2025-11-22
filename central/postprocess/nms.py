# central/postprocess/nms.py
# Python 3.9 compatible. Comments in English.
from typing import List, Tuple
import numpy as np
from ..detector.model import Detection

BBox = Tuple[int, int, int, int]

def _iou_xywh(a: BBox, b: BBox) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ax2, ay2 = ax + aw, ay + ah
    bx2, by2 = bx + bw, by + bh
    inter_x1 = max(ax, bx)
    inter_y1 = max(ay, by)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    iw = max(0, inter_x2 - inter_x1)
    ih = max(0, inter_y2 - inter_y1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    union = aw * ah + bw * bh - inter
    if union <= 0:
        return 0.0
    return float(inter / union)

def soft_nms_gaussian(dets: List[Detection],
                      sigma: float = 0.5,
                      iou_th: float = 0.6,
                      score_th: float = 0.001) -> List[Detection]:
    """Basic Gaussian Soft-NMS on [x,y,w,h] detections.
    - Decays scores of overlapping boxes instead of hard suppression.
    - Returns boxes with final scores >= score_th.
    """
    if len(dets) == 0:
        return []
    boxes = np.array([d.box for d in dets], dtype=np.float32)
    scores = np.array([d.conf for d in dets], dtype=np.float32)

    keep_boxes = []
    keep_scores = []

    while boxes.shape[0] > 0:
        m = int(np.argmax(scores))
        max_box = boxes[m].copy()
        max_score = float(scores[m])
        keep_boxes.append(tuple(int(v) for v in max_box))
        keep_scores.append(max_score)

        # remove selected
        rest_mask = np.ones((boxes.shape[0],), dtype=bool)
        rest_mask[m] = False
        rest_boxes = boxes[rest_mask]
        rest_scores = scores[rest_mask]

        # decay remaining
        if rest_boxes.shape[0] > 0:
            ious = np.array([_iou_xywh(tuple(max_box.tolist()), tuple(b.tolist())) for b in rest_boxes], dtype=np.float32)
            decay = np.exp(-(ious * ious) / max(1e-6, sigma))
            # only decay if IoU >= threshold (optional; classic Soft-NMS often decays regardless)
            mask_decay = ious >= iou_th
            rest_scores[mask_decay] = rest_scores[mask_decay] * decay[mask_decay]

            # filter by score_th
            valid = rest_scores >= score_th
            boxes = rest_boxes[valid]
            scores = rest_scores[valid]
        else:
            boxes = np.zeros((0, 4), dtype=np.float32)
            scores = np.zeros((0,), dtype=np.float32)

    # rebuild detections
    out: List[Detection] = []
    for b, s in zip(keep_boxes, keep_scores):
        out.append(Detection(box=(int(b[0]), int(b[1]), int(b[2]), int(b[3])), conf=float(s)))
    return out
