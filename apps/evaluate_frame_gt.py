from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from thesis3.core import to_serializable
from thesis3.frame_gt_evaluation import evaluate_frame_ground_truth, format_frame_gt_evaluation
from thesis3.video_data import load_frame_annotations


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate detector observations in event log against frame-level GT.")
    parser.add_argument("--event-log", required=True, help="Path to a JSONL event log.")
    parser.add_argument("--frames", required=True, help="Frame annotation JSONL.")
    parser.add_argument("--iou-threshold", type=float, default=0.5, help="Minimum IoU for a GT/detection match.")
    parser.add_argument(
        "--timestamp-tolerance-s",
        type=float,
        default=0.05,
        help="Max timestamp delta for pairing frame GT with detector observation.",
    )
    parser.add_argument(
        "--class-agnostic",
        action="store_true",
        help="Ignore class name during GT/detection matching.",
    )
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args()

    frames = load_frame_annotations(args.frames)
    summary = evaluate_frame_ground_truth(
        event_log_path=args.event_log,
        frames=frames,
        iou_threshold=args.iou_threshold,
        timestamp_tolerance_s=args.timestamp_tolerance_s,
        class_agnostic=args.class_agnostic,
    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(to_serializable(summary), indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print(format_frame_gt_evaluation(summary))
    if args.output:
        print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
