from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from thesis3.camera_inventory import (
    build_calibration_registry_template,
    build_camera_inventory_from_assets,
    export_camera_setup,
)
from thesis3.video_data import load_video_assets
from thesis3.video_probe import index_mp4_corpus


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap camera inventory and calibration registry templates.")
    parser.add_argument("--input-root", help="MP4 root directory or single MP4 file to index for camera setup.")
    parser.add_argument("--video-assets", help="Existing video asset JSONL to build camera setup from.")
    parser.add_argument("--output-dir", required=True, help="Directory for camera inventory outputs.")
    parser.add_argument(
        "--camera-strategy",
        choices=["parent", "stem", "prefix"],
        default="parent",
        help="How to infer camera_id when indexing raw MP4 input.",
    )
    parser.add_argument("--site-id", default="default_site", help="Default site_id for generated inventory.")
    parser.add_argument("--environment-tag", default="unknown", help="Default environment tag for generated inventory.")
    parser.add_argument("--timezone", help="Optional default timezone for the generated inventory.")
    parser.add_argument(
        "--stream-ref-prefix",
        default="stream_ref::",
        help="Prefix used when generating stream_uri_ref placeholders.",
    )
    parser.add_argument(
        "--safe-zone-ref-prefix",
        default="safe_zone::",
        help="Prefix used when generating safe_zone_ref placeholders.",
    )
    args = parser.parse_args()

    source_count = sum(bool(value) for value in (args.input_root, args.video_assets))
    if source_count != 1:
        parser.error("Provide exactly one of --input-root or --video-assets.")

    if args.input_root:
        assets = index_mp4_corpus(args.input_root, camera_strategy=args.camera_strategy)
    else:
        assets = load_video_assets(args.video_assets)

    inventory = build_camera_inventory_from_assets(
        assets,
        default_site_id=args.site_id,
        default_environment_tag=args.environment_tag,
        default_timezone=args.timezone,
        stream_ref_prefix=args.stream_ref_prefix,
        safe_zone_ref_prefix=args.safe_zone_ref_prefix,
    )
    calibration_registry = build_calibration_registry_template(inventory)
    written = export_camera_setup(
        inventory=inventory,
        calibration_registry=calibration_registry,
        output_dir=args.output_dir,
    )
    for label, path in sorted(written.items()):
        print(f"{label}={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
