from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from thesis3.core import load_pipeline_config
from thesis3.dataclass_compat import asdict, dataclass
from thesis3.live_runtime import execute_live_stream
from thesis3.reporting import summarize_event_log
from thesis3.runtime import execute_replay


@dataclass(slots=True)
class SuiteRunRecord:
    config_path: str
    mode: str
    event_log: str
    decision_count: int
    summary: dict[str, Any]


def run_experiment_suite(
    config_paths: list[str],
    output_path: str | Path | None = None,
    live_max_groups: int | None = None,
    live_max_seconds: float | None = None,
) -> list[SuiteRunRecord]:
    records: list[SuiteRunRecord] = []
    for config_path in config_paths:
        config = load_pipeline_config(config_path)
        is_live = isinstance(config.extra.get("live"), dict)
        if is_live:
            event_log, decisions = execute_live_stream(
                config_path=config_path,
                max_groups=live_max_groups,
                max_seconds=live_max_seconds,
            )
            mode = "live"
        else:
            event_log, decisions = execute_replay(config_path=config_path)
            mode = "replay"

        summary = summarize_event_log(event_log)
        records.append(
            SuiteRunRecord(
                config_path=str(config_path),
                mode=mode,
                event_log=event_log,
                decision_count=len(decisions),
                summary=summary,
            )
        )

    if output_path is not None:
        suite_path = Path(output_path)
        suite_path.parent.mkdir(parents=True, exist_ok=True)
        with suite_path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(asdict(record), ensure_ascii=True) + "\n")
    return records
