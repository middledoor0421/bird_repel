from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from thesis3.video_data import build_experiment_manifest, load_event_annotations, write_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an experiment manifest from event-level GT annotations.")
    parser.add_argument("--events", required=True, help="Path to the event annotation JSONL file.")
    parser.add_argument("--output", required=True, help="Output JSONL path for experiment samples.")
    parser.add_argument(
        "--negative-ratio",
        type=float,
        default=1.0,
        help="How many negative samples to include relative to positives.",
    )
    parser.add_argument(
        "--skip-hard-negative-priority",
        action="store_true",
        help="Do not always include hard negatives before sampling ordinary negatives.",
    )
    args = parser.parse_args()

    events = load_event_annotations(args.events)
    samples = build_experiment_manifest(
        events=events,
        negative_ratio=args.negative_ratio,
        include_hard_negative_always=not args.skip_hard_negative_priority,
    )
    write_jsonl(samples, args.output)
    print(f"experiment_samples={len(samples)}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
