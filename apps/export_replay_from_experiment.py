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

from thesis3.video_replay_export import (
    export_replay_bundle,
    parse_annotation_labels,
    parse_dataset_splits,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export frame images and a replay manifest from MP4-backed experiment samples."
    )
    parser.add_argument("--experiment-manifest", required=True, help="Path to experiment sample JSONL.")
    parser.add_argument("--video-index", required=True, help="Path to video asset JSONL.")
    parser.add_argument("--output-dir", required=True, help="Directory for extracted frames and replay manifest.")
    parser.add_argument("--fps", type=float, default=2.0, help="Frame extraction rate for each sample clip.")
    parser.add_argument(
        "--image-format",
        choices=["jpg", "png"],
        default="jpg",
        help="Image format for extracted frames.",
    )
    parser.add_argument(
        "--frame-annotations",
        default=None,
        help="Optional frame-level GT JSONL to attach matching bbox annotations into replay metadata.",
    )
    parser.add_argument(
        "--include-label",
        action="append",
        choices=["bird_present", "bird_absent", "hard_negative", "unknown"],
        default=None,
        help="Optional label filter. Can be repeated.",
    )
    parser.add_argument(
        "--include-split",
        action="append",
        choices=["train", "val", "test"],
        default=None,
        help="Optional split filter. Can be repeated.",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Optional limit for debugging or small dry-runs.",
    )
    args = parser.parse_args()

    summary = export_replay_bundle(
        experiment_manifest_path=args.experiment_manifest,
        video_index_path=args.video_index,
        output_dir=args.output_dir,
        extraction_fps=args.fps,
        image_format=args.image_format,
        frame_annotations_path=args.frame_annotations,
        include_labels=parse_annotation_labels(args.include_label),
        include_splits=parse_dataset_splits(args.include_split),
        max_samples=args.max_samples,
    )
    print(json.dumps(asdict(summary), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
