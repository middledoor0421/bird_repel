from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from thesis3.annotation_adjudication import (
    export_adjudication_tasks,
    format_adjudication_task_summary,
    build_adjudication_tasks,
    summarize_adjudication_tasks,
)
from thesis3.core import to_serializable
from thesis3.video_data import load_event_annotations, load_frame_annotations


def main() -> int:
    parser = argparse.ArgumentParser(description="Export unresolved annotation adjudication tasks.")
    parser.add_argument("--events", help="Event annotation JSONL to scan.")
    parser.add_argument("--frames", help="Frame annotation JSONL to scan.")
    parser.add_argument("--output-tasks", required=True, help="Output JSONL path for adjudication tasks.")
    parser.add_argument("--output-summary", help="Optional JSON summary output path.")
    args = parser.parse_args()

    if not args.events and not args.frames:
        parser.error("At least one of --events or --frames is required.")

    events = load_event_annotations(args.events) if args.events else []
    frames = load_frame_annotations(args.frames) if args.frames else []
    tasks = build_adjudication_tasks(events=events, frames=frames)
    summary = summarize_adjudication_tasks(tasks)

    output_tasks = Path(args.output_tasks)
    output_tasks.parent.mkdir(parents=True, exist_ok=True)
    export_adjudication_tasks(tasks, str(output_tasks))

    if args.output_summary:
        output_summary = Path(args.output_summary)
        output_summary.parent.mkdir(parents=True, exist_ok=True)
        output_summary.write_text(json.dumps(to_serializable(summary), indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print(format_adjudication_task_summary(summary))
    print(f"output_tasks={args.output_tasks}")
    if args.output_summary:
        print(f"output_summary={args.output_summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
