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

from thesis3.readiness import format_readiness_report, inspect_pipeline_readiness
from thesis3.suite_runner import run_experiment_suite

DEFAULT_CONFIGS = {
    "demo": [
        "configs/scenario_detector_only_baseline.example.json",
        "configs/scenario_bird_sahi_method_bundle.example.json",
        "configs/scenario_bird_sahi_noconfirm.example.json",
    ],
    "local": [
        "configs/scenario_detector_only_baseline.example.json",
        "configs/scenario_bird_sahi_method_bundle.local.json",
        "configs/scenario_bird_sahi_noconfirm.local.json",
    ],
    "local_tuned": [
        "configs/scenario_detector_only_baseline.example.json",
        "configs/scenario_bird_sahi_method_bundle_tuned.local.json",
        "configs/scenario_bird_sahi_noconfirm.local.json",
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the fixed detector-only baseline against bird-sahi variants."
    )
    parser.add_argument(
        "--profile",
        choices=sorted(DEFAULT_CONFIGS),
        default="demo",
        help="Choose demo configs or local repo-backed configs.",
    )
    parser.add_argument(
        "--config",
        action="append",
        help="Optional explicit configs. If provided, these replace the built-in profile list.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional JSONL output path for suite records.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only run readiness checks and do not execute the suite.",
    )
    parser.add_argument(
        "--allow-not-ready",
        action="store_true",
        help="Run the suite even if readiness checks report errors.",
    )
    args = parser.parse_args()

    config_paths = args.config or DEFAULT_CONFIGS[args.profile]
    reports = [inspect_pipeline_readiness(path) for path in config_paths]
    print("\n\n".join(format_readiness_report(report) for report in reports))

    if any(not report.ready for report in reports) and not args.allow_not_ready:
        return 2
    if args.check_only:
        return 0

    output_path = args.output or f"artifacts/suites/bird_sahi_focus_{args.profile}.jsonl"
    records = run_experiment_suite(config_paths=config_paths, output_path=output_path)
    print(json.dumps([asdict(record) for record in records], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
