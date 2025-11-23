# training/sahi_tile_yolo.py
# Python 3.9 compatible. Comments in English.
import argparse
from pathlib import Path
import os
from typing import List, Tuple
import cv2
import numpy as np


def load_yolo_labels(label_path: str) -> List[Tuple[int, float, float, float, float]]:
    """Load YOLO labels: class x_center y_center width height (normalized)."""
    items: List[Tuple[int, float, float, float, float]] = []
    if not os.path.exists(label_path):
        return items
    with open(label_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 5:
                continue
            cls = int(float(parts[0]))
            x = float(parts[1]); y = float(parts[2])
            w = float(parts[3]); h = float(parts[4])
            items.append((cls, x, y, w, h))
    return items


def save_yolo_labels(label_path: str, items: List[Tuple[int, float, float, float, float]]) -> None:
    with open(label_path, "w", encoding="utf-8") as f:
        for cls, x, y, w, h in items:
            f.write(f"{cls} {x:.6f} {y:.6f} {w:.6f} {h:.6f}\n")


def clip_box_to_tile(px: float, py: float, pw: float, ph: float,
                     tx: int, ty: int, tw: int, th: int) -> Tuple[float, float, float, float, bool]:
    """Clip absolute box(px,py,pw,ph) to tile rect(tx,ty,tw,th).
    Returns clipped box and keep flag (True if area ratio >= 1% by default handled outside).
    """
    x1 = px - pw * 0.5
    y1 = py - ph * 0.5
    x2 = px + pw * 0.5
    y2 = py + ph * 0.5

    cx1 = max(x1, tx)
    cy1 = max(y1, ty)
    cx2 = min(x2, tx + tw)
    cy2 = min(y2, ty + th)

    cw = max(0.0, cx2 - cx1)
    ch = max(0.0, cy2 - cy1)
    if cw <= 0.0 or ch <= 0.0:
        return 0.0, 0.0, 0.0, 0.0, False

    cxc = cx1 + cw * 0.5
    cyc = cy1 + ch * 0.5
    return cxc, cyc, cw, ch, True


def main() -> None:
    ap = argparse.ArgumentParser("Offline SAHI-like tiler for YOLO datasets")
    ap.add_argument("--images", type=str, required=True, help="Input images folder")
    ap.add_argument("--labels", type=str, required=True, help="Input labels folder (YOLO txt)")
    ap.add_argument("--out_images", type=str, required=True, help="Output images folder")
    ap.add_argument("--out_labels", type=str, required=True, help="Output labels folder")
    ap.add_argument("--tile", type=int, default=896, help="Tile size (square)")
    ap.add_argument("--overlap", type=float, default=0.25, help="Overlap ratio [0~0.9]")
    ap.add_argument("--min_area_ratio", type=float, default=0.01, help="Min kept area ratio vs original box")
    args = ap.parse_args()

    Path(args.out_images).mkdir(parents=True, exist_ok=True)
    Path(args.out_labels).mkdir(parents=True, exist_ok=True)

    img_files = [p for p in sorted(Path(args.images).glob("*")) if p.suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp"]]
    for ip in img_files:
        img = cv2.imread(str(ip))
        if img is None:
            continue
        h, w = img.shape[:2]
        base = ip.stem
        lp = Path(args.labels) / f"{base}.txt"
        labels = load_yolo_labels(str(lp))

        # convert labels to absolute pixels
        abs_boxes = []
        for cls, x, y, bw, bh in labels:
            px = x * w; py = y * h; pw = bw * w; ph = bh * h
            abs_boxes.append((cls, px, py, pw, ph))

        ts = int(args.tile)
        ov = max(0.0, min(args.overlap, 0.9))
        sx = max(1, int(ts * (1.0 - ov)))
        sy = sx

        xs = list(range(0, max(1, w - ts + 1), sx)) or [0]
        ys = list(range(0, max(1, h - ts + 1), sy)) or [0]

        for ty in ys:
            for tx in xs:
                tw = min(ts, w - tx)
                th = min(ts, h - ty)
                tile_img = img[ty:ty + th, tx:tx + tw]

                out_boxes = []
                for cls, px, py, pw, ph in abs_boxes:
                    cxc, cyc, cw, ch, ok = clip_box_to_tile(px, py, pw, ph, tx, ty, tw, th)
                    if not ok:
                        continue
                    # keep only boxes with reasonable overlap to avoid noisy tiny fragments
                    original_area = max(1.0, pw * ph)
                    clip_area = cw * ch
                    if clip_area / original_area < args.min_area_ratio:
                        continue
                    # normalize to tile
                    nx = cxc / float(tw)
                    ny = cyc / float(th)
                    nw = cw / float(tw)
                    nh = ch / float(th)
                    # discard degenerate boxes
                    if nw <= 0.0 or nh <= 0.0:
                        continue
                    out_boxes.append((cls, nx, ny, nw, nh))

                # skip empty tiles to save disk unless at least one box
                if len(out_boxes) == 0:
                    continue

                # write outputs
                out_name = f"{base}_x{tx}_y{ty}_t{ts}"
                cv2.imwrite(str(Path(args.out_images) / f"{out_name}.jpg"), tile_img)
                save_yolo_labels(str(Path(args.out_labels) / f"{out_name}.txt"), out_boxes)


if __name__ == "__main__":
    main()
