from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from thesis3.readiness import format_readiness_report, inspect_pipeline_readiness


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect whether a thesis3 pipeline config is ready to run.")
    parser.add_argument("--config", action="append", required=True, help="Config path to inspect. Repeat to check multiple configs.")
    parser.add_argument(
        "--skip-plugin-init",
        action="store_true",
        help="Only validate config shape, plugin names, and file paths without instantiating plugins.",
    )
    parser.add_argument(
        "--skip-external-init",
        action="store_true",
        help="Skip instantiating nested external model targets such as bird_sahi_temporal YOLO backends.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of the human-readable report.",
    )
    args = parser.parse_args()

    reports = [
        inspect_pipeline_readiness(
            config_path=config_path,
            instantiate_plugins=not args.skip_plugin_init,
            instantiate_external_targets=not args.skip_external_init,
        )
        for config_path in args.config
    ]
    exit_code = 0 if all(report.ready for report in reports) else 2
    if args.json:
        print(json.dumps([report.to_dict() for report in reports], indent=2, sort_keys=True))
    else:
        print("\n\n".join(format_readiness_report(report) for report in reports))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

