from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from thesis3.video_data import generate_clip_tasks, load_video_assets, write_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate clip-level annotation tasks from indexed MP4 assets.")
    parser.add_argument("--video-index", required=True, help="Path to the video asset JSONL file.")
    parser.add_argument("--output", required=True, help="Output JSONL path for clip tasks.")
    parser.add_argument("--clip-seconds", type=float, default=10.0, help="Clip duration in seconds.")
    parser.add_argument(
        "--stride-seconds",
        type=float,
        default=None,
        help="Stride between adjacent clip tasks. Defaults to clip length.",
    )
    parser.add_argument(
        "--drop-tail",
        action="store_true",
        help="Drop the last clip if it is shorter than the requested clip length.",
    )
    args = parser.parse_args()

    assets = load_video_assets(args.video_index)
    tasks = generate_clip_tasks(
        assets=assets,
        clip_duration_s=args.clip_seconds,
        clip_stride_s=args.stride_seconds,
        include_tail=not args.drop_tail,
    )
    write_jsonl(tasks, args.output)
    print(f"clip_tasks={len(tasks)}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
