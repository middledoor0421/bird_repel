from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from thesis3.video_data import write_jsonl
from thesis3.video_probe import index_mp4_corpus


def main() -> int:
    parser = argparse.ArgumentParser(description="Index MP4 files into a JSONL video asset manifest.")
    parser.add_argument("--input", required=True, help="Path to an MP4 file or a directory of MP4 files.")
    parser.add_argument("--output", required=True, help="Output JSONL path for the indexed assets.")
    parser.add_argument(
        "--camera-strategy",
        choices=["parent", "stem", "prefix"],
        default="parent",
        help="How to infer camera_id from each MP4 path.",
    )
    args = parser.parse_args()

    assets = index_mp4_corpus(args.input, camera_strategy=args.camera_strategy)
    write_jsonl(assets, args.output)
    print(f"indexed_assets={len(assets)}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
