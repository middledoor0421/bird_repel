# central/apps/run_infer.py
import argparse
import time
from typing import List, Tuple
import cv2
from loguru import logger

from common.config import load_yaml
from common.logger import init_logger
from common.angle import pixels_to_bearing
from common.events import BirdTarget

from central.ingest.reader import FrameReader
from central.roi_gating.gater import ROIGater, BBox
from central.detector.model import DetectorStub, soft_nms, iou_aware_score, Detection
from central.tracker.track import SimpleTracker

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser("CCS Inference (skeleton)")
    p.add_argument("--config", type=str, required=True, help="Path to CCS YAML config")
    p.add_argument("--source", type=str, required=False, default="", help="RTSP/File path (single source)")
    p.add_argument("--dry-run", action="store_true", help="Initialize components and exit")
    return p

def main() -> None:
    init_logger()
    args = build_parser().parse_args()
    cfg = load_yaml(args.config)
    logger.info("Loaded config: {}", args.config)

    # Build components from config (subset)
    ingest0 = None
    if args.source:
        ingest0 = FrameReader(uri=args.source,
                              width=cfg["ingest"]["sources"][0]["width"],
                              height=cfg["ingest"]["sources"][0]["height"],
                              fps=cfg["ingest"]["sources"][0]["fps"])

    gcfg = cfg["roi_gating"]
    gater = ROIGater(diff_th=gcfg["motion"]["diff_th"],
                     min_area=gcfg["motion"]["min_area"],
                     tile_size=gcfg["tiles"]["tile_size"],
                     overlap=gcfg["tiles"]["overlap"])

    dcfg = cfg["detector"]
    detector = DetectorStub(input_size=dcfg["input_size"],
                            conf_th=dcfg["conf_th"])

    tracker = SimpleTracker()

    if args.dry_run:
        logger.info("Dry-run mode: components initialized, exiting.")
        return

    if ingest0 is None:
        raise ValueError("Please provide --source for a demo run.")

    cx, cy = cfg["postprocess"]["angle_center"]
    fov = float(cfg["postprocess"]["calibration"]["fov_deg"])

    while True:
        ts_ms, frame = ingest0.read()
        if frame is None:
            logger.info("End of stream.")
            break

        h, w = frame.shape[:2]
        # Stage0: ROI gating (for now we just compute mask; full tiling skipped in skeleton)
        _tiles: List[BBox] = gater.moving_tiles(frame)

        # Stage1: detection (stub returns [])
        dets: List[Detection] = detector.infer(frame)
        dets = soft_nms(dets, sigma=dcfg["nms"]["sigma"], iou_th=dcfg["iou_th"])

        # Tracking (skeleton attaches incremental IDs)
        tracks = tracker.update(dets)

        # Emit events
        for t in tracks:
            x, y, bw, bh = t.box
            bx = x + bw * 0.5
            by = y + bh * 0.5
            bearing = pixels_to_bearing((bx, by), (w, h), (cx, cy), fov)
            event = BirdTarget(
                track_id=t.track_id,
                t=ts_ms if ts_ms is not None else int(time.time() * 1000),
                cam_id="cam-0",
                bearing=float(bearing),
                box=[float(x), float(y), float(bw), float(bh)],
                conf=float(iou_aware_score(t)),  # stub uses det.conf
                size_px=int(bw * bh),
                need_recheck=False,
                meta={"version": "skeleton"}
            )
            logger.info("Emit BirdTarget: {}", event.json())

        # Simple display for dev (press q to quit)
        cv2.imshow("ccs_skeleton", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    ingest0.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
