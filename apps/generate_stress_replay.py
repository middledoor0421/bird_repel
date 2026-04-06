from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from thesis3.stress import PRESET_STRESS_PROFILES, generate_preset_variants, load_manifest_records


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate replay manifests with synthetic stress perturbations.")
    parser.add_argument("--input-manifest", required=True, help="Base replay manifest JSONL/JSON path.")
    parser.add_argument("--output-dir", required=True, help="Directory for stressed replay manifests.")
    parser.add_argument(
        "--preset",
        action="append",
        choices=sorted(PRESET_STRESS_PROFILES),
        required=True,
        help="Repeat to generate multiple preset stress variants.",
    )
    parser.add_argument("--seed", type=int, default=0, help="Base random seed.")
    args = parser.parse_args()

    written = generate_preset_variants(
        args.input_manifest,
        output_dir=args.output_dir,
        preset_names=args.preset,
        seed=args.seed,
    )
    input_count = len(load_manifest_records(args.input_manifest))
    summary_path = Path(args.output_dir) / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "input_manifest": args.input_manifest,
                "input_record_count": input_count,
                "seed": args.seed,
                "variants": written,
            },
            indent=2,
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )
    for preset_name, output_path in sorted(written.items()):
        print(f"{preset_name}={output_path}")
    print(f"summary={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
