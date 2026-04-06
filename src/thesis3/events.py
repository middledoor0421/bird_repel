from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from thesis3.core import to_serializable


class JsonlEventStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event_type: str, payload: Any, timestamp: float | None = None) -> None:
        record = {
            "event_type": event_type,
            "timestamp": timestamp,
            "payload": to_serializable(payload),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")
