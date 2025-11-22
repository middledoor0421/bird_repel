# central/apps/run_multi.py
# Python 3.9 compatible. Comments in English.
import argparse
import time
import threading
from typing import Dict, List, Tuple, Optional
import cv2
from loguru import logger
import numpy as np

from common.config import load_yaml
from common.logger import init_logger
from common.angle import pixels_to_bearing
from common.events import BirdTarget

from central.ingest.capture import LatestFrameStore, CaptureWorker
from central.roi_gating.gater import ROIGater, BBox
from central.detector.model import BirdDetector, Detection
from central.tracker.byte_lite import ByteTrackLite
from central.postprocess.nms import soft_nms_gaussian
from central.postprocess.filters import filter_by_min_box
from central.sahi_runner.runner import SAHIExecutor


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser("CCS Multi-camera Inference")
    p.add_argument("--config", type=str, required=True, help="Path to CCS YAML config")
    p.add_argument("--dry-run", action="store_true", help="Initialize components and exit")
    return p


def now_ms() -> int:
    return int(time.time() * 1000)


def make_grid_2x2(images: List[np.ndarray]) -> np.ndarray:
    """Make a 2x2 mosaic. Empty slots will be black."""
    # Expect up to 4 images with same H,W,C after scaling
    cells: List[np.ndarray] = []
    for img in images:
        if img is None:
            # create a black placeholder same size as first valid cell later
            cells.append(None)  # type: ignore
        else:
            cells.append(img)
    # determine target size
    H = W = None
    for c in cells:
        if c is not None:
            H, W = c.shape[0], c.shape[1]
            break
    if H is None or W is None:
        return np.zeros((480, 640, 3), dtype=np.uint8)
    def blk() -> np.ndarray:
        return np.zeros((H, W, 3), dtype=np.uint8)
    grid = [
        cells[0] if len(cells) > 0 and cells[0] is not None else blk(),
        cells[1] if len(cells) > 1 and cells[1] is not None else blk(),
        cells[2] if len(cells) > 2 and cells[2] is not None else blk(),
        cells[3] if len(cells) > 3 and cells[3] is not None else blk(),
    ]
    top = np.hstack((grid[0], grid[1]))
    bottom = np.hstack((grid[2], grid[3]))
    return np.vstack((top, bottom))


def main() -> None:
    init_logger()
    args = build_parser().parse_args()
    cfg = load_yaml(args.config)
    logger.info("Loaded config: {}", args.config)

    # --- display config ---
    disp_cfg = cfg.get("display", {})
    show = bool(disp_cfg.get("enable", True))
    scale = float(disp_cfg.get("scale", 0.5))
    multi_mode = str(disp_cfg.get("multi", "windows"))  # "windows" or "grid"
    win_name = str(disp_cfg.get("window_name", "ccs_multi"))

    if show:
        if multi_mode == "windows":
            # per-camera windows created dynamically
            pass
        else:
            cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)

    # --- ingest sources ---
    sources = cfg["ingest"]["sources"]
    if not isinstance(sources, list) or len(sources) == 0:
        raise ValueError("Config.ingest.sources must be a non-empty list")
    # optional sync tolerance (not strictly used here, but kept for future)
    sync_cfg = cfg["ingest"].get("sync", {})
    tolerance_ms = int(sync_cfg.get("tolerance_ms", 80))

    # --- build per-camera capture workers ---
    stores: Dict[str, LatestFrameStore] = {}
    workers: Dict[str, CaptureWorker] = {}
    for s in sources:
        cam_id = str(s["id"])
        store = LatestFrameStore()
        stores[cam_id] = store
        w = CaptureWorker(cam_id=cam_id,
                          uri=str(s["uri"]),
                          width=int(s["width"]),
                          height=int(s["height"]),
                          fps=int(s["fps"]),
                          store=store)
        workers[cam_id] = w

    # --- per-camera ROIGater / Tracker / SAHI cooldown ---
    gcfg = cfg["roi_gating"]
    gaters: Dict[str, ROIGater] = {}
    for cam_id in stores.keys():
        gaters[cam_id] = ROIGater(diff_th=gcfg["motion"]["diff_th"],
                                  min_area=gcfg["motion"]["min_area"],
                                  tile_size=gcfg["tiles"]["tile_size"],
                                  overlap=gcfg["tiles"]["overlap"])

    tcfg = cfg["tracker"]
    trackers: Dict[str, ByteTrackLite] = {}
    for cam_id in stores.keys():
        trackers[cam_id] = ByteTrackLite(
            match_iou_th=float(tcfg["match_iou_th"]),
            conf_th_high=float(tcfg["conf_th_high"]),
            conf_th_low=float(tcfg["conf_th_low"]),
            track_buffer=int(tcfg["track_buffer"]),
        )

    scfg = cfg.get("sahi", {})
    sahi_enabled = bool(scfg.get("enable", True))
    sahi_exec = SAHIExecutor(
        tile_size=int(scfg.get("tile_size", 896)),
        overlap=float(scfg.get("overlap", 0.25)),
        merge_iou=float(scfg.get("postprocess", {}).get("merge_iou", 0.55)),
        sigma=float(cfg["detector"]["nms"].get("sigma", 0.5)),
        max_tiles=int(scfg.get("max_tiles", 6)),
    )
    sahi_cooldown_ms = int(scfg.get("cooldown_ms", 600))
    last_sahi_ms: Dict[str, int] = {cid: 0 for cid in stores.keys()}

    # --- detector (single instance, run on main thread) ---
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

    # --- postprocess / event guard ---
    pcfg = cfg["postprocess"]
    min_box = int(pcfg.get("min_box_size", 6))
    cx, cy = pcfg["angle_center"]
    fov = float(pcfg["calibration"]["fov_deg"])

    ecfg = cfg["event"]
    emit_conf_th = float(ecfg.get("emit_conf_th", 0.15))

    # --- ROI policy triggers for SAHI ---
    policy = gcfg["policy"]
    small_ratio = float(policy.get("small_area_ratio", 0.002))
    conf_low = float(policy.get("conf_low", 0.2))

    # --- telemetry ---
    metrics_cfg = cfg.get("metrics", {})
    log_interval = float(metrics_cfg.get("interval_sec", 5.0))
    last_log_t = time.time()
    # per-cam counters
    counters: Dict[str, Dict[str, float]] = {}
    for cid in stores.keys():
        counters[cid] = {
            "frames_used": 0.0,
            "frames_dropped": 0.0,
            "events": 0.0,
            "sahi_triggers": 0.0,
            "t0": time.time()
        }

    # --- start capture workers ---
    for w in workers.values():
        w.start()

    if args.dry_run:
        logger.info("Dry-run mode: workers started; exiting without inference.")
        for w in workers.values():
            w.stop()
            w.join(timeout=2.0)
        return

    # display helpers
    first_resize_done: Dict[str, bool] = {cid: False for cid in stores.keys()}
    last_disp: Dict[str, Optional[np.ndarray]] = {cid: None for cid in stores.keys()}

    # --- round-robin inference loop ---
    cam_ids = list(stores.keys())
    idx = 0
    try:
        while True:
            cam_id = cam_ids[idx]
            idx = (idx + 1) % len(cam_ids)

            # pop latest frame for this camera (non-blocking)
            ts_ms, frame, dropped = stores[cam_id].pop_latest()
            if dropped > 0:
                counters[cam_id]["frames_dropped"] += float(dropped)

            if frame is None:
                # no new frame for this cam; short sleep to avoid busy spin
                time.sleep(0.001)
                # handle display in grid mode with last_disp images
                if show and multi_mode == "grid":
                    # refresh mosaic at a modest rate
                    pass
                # try next camera
                continue

            h, w = frame.shape[:2]
            image_area = int(w * h)

            # Stage0: ROI gating (moving tiles; later used in SAHI select)
            tiles_moving: List[BBox] = gaters[cam_id].moving_tiles(frame)

            # Stage1: detection
            dets: List[Detection] = detector.infer(frame)
            dets = filter_by_min_box(dets, min_box)

            # conditional SAHI trigger with cooldown
            promote = False
            weak_boxes: List[BBox] = []
            for d in dets:
                x, y, bw, bh = d.box
                if (bw * bh) / max(1.0, float(image_area)) < small_ratio or d.conf < conf_low:
                    promote = True
                    weak_boxes.append(d.box)

            did_sahi = False
            if sahi_enabled and promote:
                now_t = now_ms()
                if (now_t - last_sahi_ms[cam_id]) >= sahi_cooldown_ms:
                    # select tiles intersecting weak boxes; fall back to moving tiles
                    sel_tiles = sahi_exec.select_tiles((h, w), triggers=weak_boxes if len(weak_boxes) > 0 else tiles_moving)
                    sahi_dets = sahi_exec.run(frame, detector, sel_tiles)
                    dets_merged = dets + sahi_dets
                    dets = soft_nms_gaussian(dets_merged, sigma=soft_sigma, iou_th=iou_th, score_th=0.001)
                    last_sahi_ms[cam_id] = now_t
                    counters[cam_id]["sahi_triggers"] += 1.0
                    did_sahi = True
            # optional Soft-NMS even without SAHI
            if not did_sahi and use_soft_nms:
                dets = soft_nms_gaussian(dets, sigma=soft_sigma, iou_th=iou_th, score_th=0.001)

            # tracking
            tracks = trackers[cam_id].update(dets)

            # emit events
            ev_local = 0
            for t in tracks:
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
                    t=ts_ms if ts_ms is not None else now_ms(),
                    cam_id=cam_id,
                    bearing=float(bearing),
                    box=[float(x), float(y), float(bw), float(bh)],
                    conf=float(t.conf),
                    size_px=size_px,
                    need_recheck=bool(need_recheck),
                    meta={"version": "multi"},
                )
                logger.info("Emit BirdTarget [{}]: {}", cam_id, event.json())
                ev_local += 1

            # metrics update
            counters[cam_id]["frames_used"] += 1.0
            counters[cam_id]["events"] += float(ev_local)

            # display
            if show:
                # scale image
                disp = frame
                if scale != 1.0:
                    disp = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
                last_disp[cam_id] = disp

                if multi_mode == "windows":
                    win_cam = f"{win_name}-{cam_id}"
                    cv2.namedWindow(win_cam, cv2.WINDOW_NORMAL)
                    # force window size on first show
                    if not first_resize_done[cam_id]:
                        dh, dw = disp.shape[:2]
                        cv2.resizeWindow(win_cam, int(dw), int(dh))
                        first_resize_done[cam_id] = True
                    cv2.imshow(win_cam, disp)
                else:
                    # 2x2 grid
                    ordered = [last_disp.get(cid, None) for cid in cam_ids]
                    mosaic = make_grid_2x2([img for img in ordered])
                    if win_name not in [w for w in []]:
                        # ensure window exists
                        pass
                    cv2.imshow(win_name, mosaic)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            # periodic telemetry log
            if (time.time() - last_log_t) >= log_interval:
                parts = []
                for cid in cam_ids:
                    dt = max(1e-6, time.time() - counters[cid]["t0"])
                    fps = counters[cid]["frames_used"] / dt
                    parts.append(
                        f"{cid}: fps={fps:.1f}, drop={int(counters[cid]['frames_dropped'])}, "
                        f"sahi={int(counters[cid]['sahi_triggers'])}, events={int(counters[cid]['events'])}"
                    )
                logger.info("[telemetry] {}", " | ".join(parts))
                last_log_t = time.time()

        # end while
    finally:
        for w in workers.values():
            w.stop()
        for w in workers.values():
            w.join(timeout=2.0)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
