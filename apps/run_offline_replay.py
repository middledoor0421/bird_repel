from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from thesis3.runtime import execute_replay


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an offline replay for thesis3.")
    parser.add_argument("--config", required=True, help="Path to a JSON/YAML pipeline config.")
    args = parser.parse_args()

    event_log, decisions = execute_replay(args.config, emulate_realtime=False)
    print(f"event_log={event_log}")
    print(f"decisions={len(decisions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
