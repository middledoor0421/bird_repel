from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from thesis3.live_runtime import execute_live_stream


def main() -> int:
    parser = argparse.ArgumentParser(description="Run thesis3 on live or pseudo-live video streams.")
    parser.add_argument("--config", required=True, help="Path to a JSON/YAML pipeline config.")
    parser.add_argument(
        "--max-groups",
        type=int,
        default=None,
        help="Optional limit on the number of grouped live ticks to process.",
    )
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=None,
        help="Optional wall-clock limit for the live run.",
    )
    args = parser.parse_args()

    event_log, decisions = execute_live_stream(
        config_path=args.config,
        max_groups=args.max_groups,
        max_seconds=args.max_seconds,
    )
    print(f"event_log={event_log}")
    print(f"decisions={len(decisions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
