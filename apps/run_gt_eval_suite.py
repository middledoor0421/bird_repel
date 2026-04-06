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
from thesis3.gt_eval_suite import format_gt_eval_suite, normalize_suite_entries, run_gt_eval_suite
from thesis3.video_data import load_event_annotations, load_frame_annotations


def main() -> int:
    parser = argparse.ArgumentParser(description="Run event/frame GT evaluation over multiple event logs.")
    parser.add_argument(
        "--entry",
        action="append",
        required=True,
        help="Suite entry as LABEL=PATH or just PATH.",
    )
    parser.add_argument("--events", help="Optional event annotation JSONL.")
    parser.add_argument("--frames", help="Optional frame annotation JSONL.")
    parser.add_argument("--tracking-frames", help="Optional frame annotation JSONL for tracking/handoff evaluation.")
    parser.add_argument("--verification-frames", help="Optional frame annotation JSONL for verification evaluation.")
    parser.add_argument("--event-overlap-tolerance-s", type=float, default=0.0)
    parser.add_argument("--frame-iou-threshold", type=float, default=0.5)
    parser.add_argument("--frame-timestamp-tolerance-s", type=float, default=0.05)
    parser.add_argument("--frame-class-agnostic", action="store_true")
    parser.add_argument("--tracking-timestamp-tolerance-s", type=float, default=0.05)
    parser.add_argument("--verification-iou-threshold", type=float, default=0.1)
    parser.add_argument("--verification-timestamp-tolerance-s", type=float, default=0.05)
    parser.add_argument("--verification-class-agnostic", action="store_true")
    parser.add_argument("--output", required=True, help="Output JSON path.")
    args = parser.parse_args()

    events = load_event_annotations(args.events) if args.events else []
    frames = load_frame_annotations(args.frames) if args.frames else []
    tracking_frames = load_frame_annotations(args.tracking_frames) if args.tracking_frames else []
    verification_frames = load_frame_annotations(args.verification_frames) if args.verification_frames else []
    summary = run_gt_eval_suite(
        entries=normalize_suite_entries(args.entry),
        events=events,
        frames=frames,
        tracking_frames=tracking_frames,
        verification_frames=verification_frames,
        event_overlap_tolerance_s=args.event_overlap_tolerance_s,
        frame_iou_threshold=args.frame_iou_threshold,
        frame_timestamp_tolerance_s=args.frame_timestamp_tolerance_s,
        frame_class_agnostic=args.frame_class_agnostic,
        tracking_timestamp_tolerance_s=args.tracking_timestamp_tolerance_s,
        verification_iou_threshold=args.verification_iou_threshold,
        verification_timestamp_tolerance_s=args.verification_timestamp_tolerance_s,
        verification_class_agnostic=args.verification_class_agnostic,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(to_serializable(summary), indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print(format_gt_eval_suite(summary))
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
