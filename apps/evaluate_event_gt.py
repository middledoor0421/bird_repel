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
from thesis3.gt_evaluation import evaluate_event_ground_truth, format_event_gt_evaluation
from thesis3.video_data import load_event_annotations


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate thesis3 event log against event-level GT annotations.")
    parser.add_argument("--event-log", required=True, help="Path to a JSONL event log.")
    parser.add_argument("--events", required=True, help="Event annotation JSONL.")
    parser.add_argument(
        "--overlap-tolerance-s",
        type=float,
        default=0.0,
        help="Tolerance added on both sides of the GT event interval.",
    )
    parser.add_argument(
        "--positive-action-state",
        action="append",
        dest="positive_action_states",
        default=[],
        help="Action state counted as a system alert. Repeatable.",
    )
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args()

    positive_action_states = set(args.positive_action_states) if args.positive_action_states else None
    events = load_event_annotations(args.events)
    summary = evaluate_event_ground_truth(
        event_log_path=args.event_log,
        events=events,
        overlap_tolerance_s=args.overlap_tolerance_s,
        alert_action_states=positive_action_states,
    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(to_serializable(summary), indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print(format_event_gt_evaluation(summary))
    if args.output:
        print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
