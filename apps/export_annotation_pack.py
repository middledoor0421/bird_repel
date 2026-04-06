from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from thesis3.video_annotation_pack import export_annotation_pack


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export preview clips and an annotation template from clip tasks."
    )
    parser.add_argument("--clip-tasks", required=True, help="Path to clip task JSONL.")
    parser.add_argument("--output-dir", required=True, help="Directory to write the annotation pack.")
    parser.add_argument(
        "--scale-width",
        type=int,
        default=640,
        help="Resize previews to this width. Set 0 to keep original size.",
    )
    parser.add_argument(
        "--max-tasks",
        type=int,
        default=None,
        help="Optional limit for small dry-runs.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite preview clips if they already exist.",
    )
    args = parser.parse_args()

    summary = export_annotation_pack(
        clip_tasks_path=args.clip_tasks,
        output_dir=args.output_dir,
        scale_width=(args.scale_width if args.scale_width > 0 else None),
        overwrite=args.overwrite,
        max_tasks=args.max_tasks,
    )
    print(json.dumps(asdict(summary), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
