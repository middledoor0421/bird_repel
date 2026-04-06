from __future__ import annotations

import hashlib
from typing import Any

from thesis3.core import ActionState, DecisionRecord


class ActuatorSimulator:
    def __init__(self, enabled: bool = True, failure_rate: float = 0.0) -> None:
        self.enabled = enabled
        self.failure_rate = max(0.0, min(1.0, failure_rate))

    def dispatch(self, decision: DecisionRecord) -> dict[str, Any] | None:
        if not self.enabled or decision.action_state is not ActionState.SIMULATED_ACTION:
            return None

        raw = hashlib.sha256(decision.track_id.encode("utf-8")).hexdigest()
        pseudo_random = (int(raw[:8], 16) % 10000) / 10000.0
        success = pseudo_random >= self.failure_rate
        return {
            "track_id": decision.track_id,
            "action_state": decision.action_state.value,
            "status": "success" if success else "failed",
        }
