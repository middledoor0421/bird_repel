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
from central.detector.model import BirdDetector, Detection
from central.tracker.byte_lite import ByteTrackLite
from central.postprocess.nms import soft_nms_gaussian
from central.postprocess.filters import filter_by_min_box
from central.sahi_runner.runner import SAHIExecutor

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser("CCS Inference (MVP+ Step5)")
    p.add_argument("--config", type=str, required=True, help="Path to CCS YAML config")
    p.add_argument("--source", type=str, required=False, default="", help="RTSP/File path (single source)")
    p.add_argument("--dry-run", action="store_true", help="Initialize components and exit")
    return p

def main() -> None:
    init_logger()
    args = build_parser().parse_args()
    cfg = load_yaml(args.config)
    logger.info("Loaded config: {}", args.config)

    # --- display config (READ FROM ROOT 'display') ---
    disp_cfg = cfg.get("display", {})  # <= ensure we read from root
    win_name = disp_cfg.get("window_name", "ccs_mvp")
    scale = float(disp_cfg.get("scale", 1.0))
    show = bool(disp_cfg.get("enable", True))
    first_resize_done = False

    if show:
        # Create a resizable window; we will force its size on the first frame
        cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
        # Keep aspect ratio when user drags the window (best-effort)
        try:
            cv2.setWindowProperty(win_name, cv2.WND_PROP_ASPECT_RATIO, cv2.WINDOW_KEEPRATIO)
        except Exception:
            pass

    # --- ingest ---
    ingest0 = None
    if args.source:
        ingest0 = FrameReader(uri=args.source,
                              width=cfg["ingest"]["sources"][0]["width"],
                              height=cfg["ingest"]["sources"][0]["height"],
                              fps=cfg["ingest"]["sources"][0]["fps"])

    # --- roi gating ---
    gcfg = cfg["roi_gating"]
    gater = ROIGater(diff_th=gcfg["motion"]["diff_th"],
                     min_area=gcfg["motion"]["min_area"],
                     tile_size=gcfg["tiles"]["tile_size"],
                     overlap=gcfg["tiles"]["overlap"])

    # --- detector ---
    dcfg = cfg["detector"]
    detector = BirdDetector(
        weights=dcfg["weights"],
        device=cfg["runtime"]["device"],
        input_size=dcfg["input_size"],
        conf_th=dcfg["conf_th"],
        iou_th=dcfg["iou_th"],
        only_bird=dcfg["classes"]["only_bird"],
    )
    use_soft_nms = (dcfg["nms"]["type"] == "soft-nms")
    soft_sigma = float(dcfg["nms"].get("sigma", 0.5))
    iou_th = float(dcfg.get("iou_th", 0.6))

    # --- tracker ---
    tcfg = cfg["tracker"]
    tracker = ByteTrackLite(
        match_iou_th=float(tcfg["match_iou_th"]),
        conf_th_high=float(tcfg["conf_th_high"]),
        conf_th_low=float(tcfg["conf_th_low"]),
        track_buffer=int(tcfg["track_buffer"]),
    )

    # --- sahi executor ---
    scfg = cfg.get("sahi", {})
    sahi_enabled = bool(scfg.get("enable", True))
    sahi_exec = SAHIExecutor(
        tile_size=int(scfg.get("tile_size", 896)),
        overlap=float(scfg.get("overlap", 0.25)),
        merge_iou=float(scfg.get("postprocess", {}).get("merge_iou", 0.55)),
        sigma=soft_sigma,
        max_tiles=int(scfg.get("max_tiles", 6))
    )

    # --- postprocess/event guard ---
    pcfg = cfg["postprocess"]
    min_box = int(pcfg.get("min_box_size", 6))
    cx, cy = pcfg["angle_center"]
    fov = float(pcfg["calibration"]["fov_deg"])

    ecfg = cfg["event"]
    emit_conf_th = float(ecfg.get("emit_conf_th", 0.15))

    # --- roi policy triggers for SAHI ---
    policy = gcfg["policy"]
    small_ratio = float(policy.get("small_area_ratio", 0.002))
    conf_low = float(policy.get("conf_low", 0.2))

    if args.dry_run:
        logger.info("Dry-run mode: components initialized, exiting.")
        return

    if ingest0 is None:
        raise ValueError("Please provide --source for a demo run.")

    # metrics
    sahi_triggers = 0
    ev_count = 0
    t0 = time.time()

    while True:
        ts_ms, frame = ingest0.read()
        if frame is None:
            logger.info("End of stream.")
            break

        h, w = frame.shape[:2]
        image_area = int(w * h)

        # Stage0: ROI gating (mask computed; using tiles for SAHI selection later)
        moving_tiles: List[BBox] = gater.moving_tiles(frame)

        # Stage1: detection
        dets: List[Detection] = detector.infer(frame)

        # Event guard (min size prefilter)
        dets = filter_by_min_box(dets, min_box)

        # Conditional SAHI trigger (one-shot)
        promote = False
        weak_boxes: List[BBox] = []
        for d in dets:
            x, y, bw, bh = d.box
            if (bw * bh) / max(1.0, float(image_area)) < small_ratio or d.conf < conf_low:
                promote = True
                weak_boxes.append(d.box)

        if sahi_enabled and promote:
            # choose tiles intersecting weak boxes, fall back to moving tiles
            tiles = sahi_exec.select_tiles((h, w), triggers=weak_boxes if len(weak_boxes) > 0 else moving_tiles)
            sahi_dets = sahi_exec.run(frame, detector, tiles)
            # merge original + sahi via Soft-NMS
            dets_merged = dets + sahi_dets
            dets = soft_nms_gaussian(dets_merged, sigma=soft_sigma, iou_th=iou_th, score_th=0.001)
            sahi_triggers += 1
        else:
            # optional Soft-NMS even without SAHI
            if use_soft_nms:
                dets = soft_nms_gaussian(dets, sigma=soft_sigma, iou_th=iou_th, score_th=0.001)

        # Tracking
        tracks = tracker.update(dets)

        # Emit events (with emit threshold and need_recheck)
        for t in tracks:
            # guard by emit_conf_th
            if float(t.conf) < emit_conf_th:
                continue
            x, y, bw, bh = t.box
            bx = x + bw * 0.5
            by = y + bh * 0.5
            bearing = pixels_to_bearing((bx, by), (w, h), (cx, cy), fov)
            size_px = int(bw * bh)
            need_recheck = (float(size_px) / float(image_area) < small_ratio) or (float(t.conf) < conf_low)

            event = BirdTarget(
                track_id=t.track_id,
                t=ts_ms if ts_ms is not None else int(time.time() * 1000),
                cam_id="cam-0",
                bearing=float(bearing),
                box=[float(x), float(y), float(bw), float(bh)],
                conf=float(t.conf),
                size_px=size_px,
                need_recheck=bool(need_recheck),
                meta={"version": "mvp_step5"}
            )
            ev_count += 1
            logger.info("Emit BirdTarget: {}", event.json())

        # --- display (scaled) ---
        if show:
            # 1) scale the image content
            if scale != 1.0:
                disp = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            else:
                disp = frame

            # 2) FORCE window size once (so scale visibly changes window size)
            if not first_resize_done:
                dh, dw = disp.shape[:2]  # note: shape is (h, w, c)
                cv2.resizeWindow(win_name, int(dw), int(dh))
                first_resize_done = True

            cv2.imshow(win_name, disp)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        # periodic metrics
        if (ev_count + sahi_triggers) % 50 == 0:
            dt = time.time() - t0
            fps = (ev_count + 1) / max(1e-6, dt)
            logger.info("Metrics: events={}, sahi_triggers={}, elapsed={:.1f}s, approx_fps={:.2f}",
                        ev_count, sahi_triggers, dt, fps)

    ingest0.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
