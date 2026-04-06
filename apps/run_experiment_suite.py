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

from thesis3.suite_runner import run_experiment_suite


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run multiple thesis3 configs and collect per-run summaries."
    )
    parser.add_argument(
        "--config",
        action="append",
        required=True,
        help="Config path. Repeat this flag to run multiple experiments.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional JSONL output path for suite records.",
    )
    parser.add_argument(
        "--live-max-groups",
        type=int,
        default=None,
        help="Optional max_groups forwarded to live runs.",
    )
    parser.add_argument(
        "--live-max-seconds",
        type=float,
        default=None,
        help="Optional max_seconds forwarded to live runs.",
    )
    args = parser.parse_args()

    records = run_experiment_suite(
        config_paths=args.config,
        output_path=args.output,
        live_max_groups=args.live_max_groups,
        live_max_seconds=args.live_max_seconds,
    )
    print(json.dumps([asdict(record) for record in records], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
