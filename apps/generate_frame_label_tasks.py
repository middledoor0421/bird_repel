from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from thesis3.video_data import (
    generate_frame_label_tasks,
    load_event_annotations,
    load_video_assets,
    write_jsonl,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate frame-level box annotation tasks from positive events.")
    parser.add_argument("--events", required=True, help="Path to the event annotation JSONL file.")
    parser.add_argument("--video-index", required=True, help="Path to the video asset JSONL file.")
    parser.add_argument("--output", required=True, help="Output JSONL path for frame label tasks.")
    parser.add_argument(
        "--max-frames-per-event",
        type=int,
        default=5,
        help="Maximum number of frame label tasks to create per positive event.",
    )
    parser.add_argument(
        "--no-boundary-frames",
        action="store_true",
        help="Do not force start/end boundary timestamps into the sampled frame tasks.",
    )
    args = parser.parse_args()

    events = load_event_annotations(args.events)
    assets = {asset.asset_id: asset for asset in load_video_assets(args.video_index)}
    tasks = generate_frame_label_tasks(
        events=events,
        assets_by_id=assets,
        max_frames_per_event=args.max_frames_per_event,
        include_boundary_frames=not args.no_boundary_frames,
    )
    write_jsonl(tasks, args.output)
    print(f"frame_label_tasks={len(tasks)}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
