from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from thesis3.gt_eval_report import render_gt_eval_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Render GT evaluation suite JSON to markdown report.")
    parser.add_argument("--suite-json", required=True, help="Path to GT evaluation suite JSON.")
    parser.add_argument("--output", required=True, help="Markdown output path.")
    args = parser.parse_args()

    summary = json.loads(Path(args.suite_json).read_text(encoding="utf-8"))
    markdown = render_gt_eval_report(summary)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")

    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
