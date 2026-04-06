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
from thesis3.camera_inventory import load_calibration_registry, load_camera_inventory
from thesis3.data_audit import audit_replay_manifest, audit_video_assets, format_audit_report
from thesis3.video_data import load_video_assets, write_jsonl
from thesis3.video_probe import index_mp4_corpus


def main() -> int:
    parser = argparse.ArgumentParser(description="Run metadata/quality audit over indexed MP4 assets or replay manifests.")
    parser.add_argument("--input-root", help="MP4 root directory or single MP4 file to index and audit.")
    parser.add_argument("--video-assets", help="Existing indexed video asset JSONL to audit.")
    parser.add_argument("--replay-manifest", help="Replay manifest JSONL/JSON to audit.")
    parser.add_argument("--output", required=True, help="JSON path to store the audit report.")
    parser.add_argument(
        "--camera-strategy",
        choices=["parent", "stem", "prefix"],
        default="parent",
        help="How to infer camera_id when indexing raw MP4 input.",
    )
    parser.add_argument(
        "--sample-frames-per-asset",
        type=int,
        default=0,
        help="Sample this many frames per MP4 asset for basic brightness/contrast/sharpness estimates.",
    )
    parser.add_argument(
        "--inspect-images",
        action="store_true",
        help="For replay manifests, compute quality metrics from image_ref files when available.",
    )
    parser.add_argument(
        "--max-inspected-frames",
        type=int,
        help="Cap the number of replay frames inspected for image-based quality metrics.",
    )
    parser.add_argument(
        "--write-indexed-assets",
        help="Optional JSONL path to persist the indexed assets when using --input-root.",
    )
    parser.add_argument("--camera-inventory", help="Optional camera inventory JSONL for metadata coverage checks.")
    parser.add_argument(
        "--calibration-registry",
        help="Optional calibration registry JSONL for calibration coverage checks.",
    )
    args = parser.parse_args()

    source_count = sum(bool(value) for value in (args.input_root, args.video_assets, args.replay_manifest))
    if source_count != 1:
        parser.error("Provide exactly one of --input-root, --video-assets, or --replay-manifest.")

    camera_inventory = load_camera_inventory(args.camera_inventory) if args.camera_inventory else None
    calibration_registry = load_calibration_registry(args.calibration_registry) if args.calibration_registry else None

    if args.input_root:
        assets = index_mp4_corpus(args.input_root, camera_strategy=args.camera_strategy)
        if args.write_indexed_assets:
            write_jsonl(assets, args.write_indexed_assets)
        report = audit_video_assets(
            assets,
            sample_frames_per_asset=args.sample_frames_per_asset,
            camera_inventory=camera_inventory,
            calibration_registry=calibration_registry,
        )
    elif args.video_assets:
        report = audit_video_assets(
            load_video_assets(args.video_assets),
            sample_frames_per_asset=args.sample_frames_per_asset,
            camera_inventory=camera_inventory,
            calibration_registry=calibration_registry,
        )
    else:
        report = audit_replay_manifest(
            args.replay_manifest,
            inspect_images=args.inspect_images,
            max_inspected_frames=args.max_inspected_frames,
            camera_inventory=camera_inventory,
            calibration_registry=calibration_registry,
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(to_serializable(report), indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(format_audit_report(report))
    print(f"output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
