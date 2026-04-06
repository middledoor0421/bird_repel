from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from thesis3.reporting import summarize_event_log


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize a thesis3 event log.")
    parser.add_argument("--event-log", required=True, help="Path to a JSONL event log.")
    args = parser.parse_args()

    summary = summarize_event_log(args.event_log)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
