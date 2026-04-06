from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from thesis3.canonical_data import (
    LabelStatus,
    SplitTag,
    export_canonical_dataset,
    load_calibration_map,
)
from thesis3.camera_inventory import load_calibration_registry, load_camera_inventory
from thesis3.video_data import load_video_assets


def main() -> int:
    parser = argparse.ArgumentParser(description="Export canonical sequence/frame schema files.")
    parser.add_argument("--video-assets", help="Indexed video asset JSONL to export as canonical sequences.")
    parser.add_argument("--replay-manifest", help="Replay manifest to export as canonical frame samples.")
    parser.add_argument("--output-dir", required=True, help="Directory for canonical outputs.")
    parser.add_argument("--environment-tag", default="unknown", help="Environment tag for the canonical records.")
    parser.add_argument("--calibration-map", help="Optional JSON mapping of camera_id -> calibration_ref.")
    parser.add_argument("--camera-inventory", help="Optional camera inventory JSONL to enrich canonical records.")
    parser.add_argument(
        "--calibration-registry",
        help="Optional calibration registry JSONL to enrich canonical records.",
    )
    parser.add_argument(
        "--split-tag",
        choices=[member.value for member in SplitTag],
        default=SplitTag.UNSPECIFIED.value,
        help="Default split tag when the source does not provide one.",
    )
    parser.add_argument(
        "--label-status",
        choices=[member.value for member in LabelStatus],
        default=LabelStatus.UNLABELED.value,
        help="Default label status when the source does not provide one.",
    )
    args = parser.parse_args()

    if not args.video_assets and not args.replay_manifest:
        parser.error("At least one of --video-assets or --replay-manifest is required.")

    calibration_map = load_calibration_map(args.calibration_map)
    camera_inventory = load_camera_inventory(args.camera_inventory) if args.camera_inventory else None
    calibration_registry = load_calibration_registry(args.calibration_registry) if args.calibration_registry else None
    video_assets = load_video_assets(args.video_assets) if args.video_assets else None
    written = export_canonical_dataset(
        video_assets=video_assets,
        replay_manifest_path=args.replay_manifest,
        output_dir=args.output_dir,
        environment_tag=args.environment_tag,
        calibration_map=calibration_map,
        camera_inventory=camera_inventory,
        calibration_registry=calibration_registry,
        default_split_tag=SplitTag(args.split_tag),
        default_label_status=LabelStatus(args.label_status),
    )

    for label, path in sorted(written.items()):
        print(f"{label}={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
