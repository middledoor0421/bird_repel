from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from thesis3.annotation_rules import (
    format_annotation_validation_report,
    load_annotation_vocabulary,
    validate_annotations,
)
from thesis3.core import to_serializable
from thesis3.video_data import (
    load_event_annotations,
    load_frame_annotations,
    load_video_assets,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate event/frame annotation JSONL files against basic GT rules.")
    parser.add_argument("--events", help="Event annotation JSONL to validate.")
    parser.add_argument("--frames", help="Frame annotation JSONL to validate.")
    parser.add_argument("--video-index", help="Video asset JSONL for duration/camera consistency checks.")
    parser.add_argument(
        "--vocabulary",
        help="Optional JSON file overriding annotation vocabulary lists.",
    )
    parser.add_argument("--output", help="Optional JSON output path for the validation report.")
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Return non-zero when warnings are present.",
    )
    args = parser.parse_args()

    if not args.events and not args.frames:
        parser.error("At least one of --events or --frames is required.")

    events = load_event_annotations(args.events) if args.events else []
    frames = load_frame_annotations(args.frames) if args.frames else []
    assets_by_id = {}
    if args.video_index:
        assets_by_id = {asset.asset_id: asset for asset in load_video_assets(args.video_index)}
    vocabulary = load_annotation_vocabulary(args.vocabulary)

    report = validate_annotations(
        events=events,
        frames=frames,
        assets_by_id=assets_by_id,
        vocabulary=vocabulary,
    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(to_serializable(report), indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print(format_annotation_validation_report(report))
    if args.output:
        print(f"output={args.output}")

    if report.error_count > 0:
        return 2
    if args.fail_on_warning and report.warning_count > 0:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
