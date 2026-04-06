from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from thesis3.annotation_queue import format_annotation_queue_summary, summarize_annotation_queue
from thesis3.core import to_serializable
from thesis3.video_data import load_event_annotations, load_frame_annotations


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize unresolved / ambiguous annotation queue state.")
    parser.add_argument("--events", help="Event annotation JSONL to summarize.")
    parser.add_argument("--frames", help="Frame annotation JSONL to summarize.")
    parser.add_argument("--output", help="Optional JSON output path for the summary.")
    args = parser.parse_args()

    if not args.events and not args.frames:
        parser.error("At least one of --events or --frames is required.")

    events = load_event_annotations(args.events) if args.events else []
    frames = load_frame_annotations(args.frames) if args.frames else []
    summary = summarize_annotation_queue(events=events, frames=frames)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(to_serializable(summary), indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print(format_annotation_queue_summary(summary))
    if args.output:
        print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
