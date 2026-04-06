from __future__ import annotations

import json
from collections import Counter
from math import ceil
from pathlib import Path
from typing import Any


def _summarize_values(values: list[float]) -> dict[str, float | int] | None:
    if not values:
        return None
    ordered = sorted(values)
    count = len(ordered)
    return {
        "count": count,
        "avg": sum(ordered) / count,
        "min": ordered[0],
        "p50": ordered[(count - 1) // 2],
        "p95": ordered[min(count - 1, max(0, ceil(count * 0.95) - 1))],
        "max": ordered[-1],
    }


def summarize_event_log(path: str | Path) -> dict[str, Any]:
    event_counter: Counter[str] = Counter()
    action_counter: Counter[str] = Counter()
    policy_counter: Counter[str] = Counter()
    trigger_reason_counter: Counter[str] = Counter()
    verification_schedule_reason_counter: Counter[str] = Counter()
    confirmation_reason_counter: Counter[str] = Counter()
    verification_failure_reason_counter: Counter[str] = Counter()
    safety_policy_reason_counter: Counter[str] = Counter()
    verification_outcome_counter: Counter[str] = Counter()
    review_required = 0
    decision_count = 0
    run_summary: dict[str, Any] = {}
    run_context: dict[str, Any] = {}
    latency_samples: dict[str, list[float]] = {
        "detector": [],
        "tracker": [],
        "verification": [],
        "policy": [],
        "actuator": [],
        "end_to_end_compute": [],
        "source_to_decision": [],
    }
    candidate_count_per_tick: list[float] = []
    selected_candidate_count_per_tick: list[float] = []
    decision_count_per_tick: list[float] = []
    verification_count_per_tick: list[float] = []

    event_log = Path(path)
    for line in event_log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        event_type = record["event_type"]
        event_counter[event_type] += 1
        payload = record["payload"]
        if event_type == "trigger_decision":
            trigger_reason_counter[str(payload.get("trigger_reason", "unknown"))] += 1
            continue
        if event_type == "verification_schedule":
            verification_schedule_reason_counter[str(payload.get("reason", "unknown"))] += 1
            continue
        if event_type == "confirmation_decision":
            confirmation_reason_counter[str(payload.get("reason", "unknown"))] += 1
            continue
        if event_type == "verification_result":
            if payload.get("verified"):
                verification_outcome_counter["verified"] += 1
            else:
                verification_outcome_counter["rejected"] += 1
                verification_failure_reason_counter[str(payload.get("failure_reason") or "unknown")] += 1
            continue
        if event_type == "safety_policy_decision":
            safety_policy_reason_counter[str(payload.get("reason", "unknown"))] += 1
            continue
        if event_type == "tick_summary":
            candidate_count_per_tick.append(float(payload.get("candidate_count", 0)))
            selected_candidate_count_per_tick.append(float(payload.get("selected_candidate_count", 0)))
            decision_count_per_tick.append(float(payload.get("decision_count", 0)))
            verification_count_per_tick.append(float(payload.get("verification_requested_count", 0)))
            continue
        if event_type == "run_start":
            run_context = {
                "run_id": payload.get("run_id"),
                "scenario": payload.get("scenario"),
                "config_hash": payload.get("config_hash"),
                "manifest_path": payload.get("manifest_path"),
                "runtime_env": payload.get("runtime_env"),
                "environment_profile": payload.get("environment_profile"),
                "method_hooks": payload.get("method_hooks"),
            }
            continue
        if event_type == "run_complete":
            run_summary = payload
            continue

        if event_type != "decision_record":
            continue
        decision_count += 1
        action_counter[payload["action_state"]] += 1
        policy_counter[payload["policy_state"]] += 1
        if payload["human_review_required"]:
            review_required += 1
        latency = payload.get("latency") or {}
        if latency.get("detector_latency_ms") is not None:
            latency_samples["detector"].append(float(latency["detector_latency_ms"]))
        if latency.get("tracker_latency_ms") is not None:
            latency_samples["tracker"].append(float(latency["tracker_latency_ms"]))
        if latency.get("verification_latency_ms") is not None:
            latency_samples["verification"].append(float(latency["verification_latency_ms"]))
        if latency.get("policy_latency_ms") is not None:
            latency_samples["policy"].append(float(latency["policy_latency_ms"]))
        if latency.get("actuator_latency_ms") is not None:
            latency_samples["actuator"].append(float(latency["actuator_latency_ms"]))
        if latency.get("end_to_end_compute_latency_ms") is not None:
            latency_samples["end_to_end_compute"].append(float(latency["end_to_end_compute_latency_ms"]))
        if latency.get("source_to_decision_latency_ms") is not None:
            latency_samples["source_to_decision"].append(float(latency["source_to_decision_latency_ms"]))

    return {
        "event_types": dict(event_counter),
        "actions": dict(action_counter),
        "policy_states": dict(policy_counter),
        "review_required_count": review_required,
        "run_context": run_context,
        "run_summary": run_summary,
        "reason_counters": {
            "trigger_reasons": dict(trigger_reason_counter),
            "verification_schedule_reasons": dict(verification_schedule_reason_counter),
            "confirmation_reasons": dict(confirmation_reason_counter),
            "verification_outcomes": dict(verification_outcome_counter),
            "verification_failure_reasons": dict(verification_failure_reason_counter),
            "safety_policy_reasons": dict(safety_policy_reason_counter),
        },
        "latency_ms": {
            stage_name: _summarize_values(values)
            for stage_name, values in latency_samples.items()
        },
        "burden": {
            "decision_count": decision_count,
            "tick_count": int(event_counter.get("tick_summary", 0)),
            "review_rate": (review_required / decision_count) if decision_count else 0.0,
            "verification_request_count": int(sum(verification_count_per_tick)),
            "verification_requests_per_tick": _summarize_values(verification_count_per_tick),
            "verification_request_rate_per_decision": (
                sum(verification_count_per_tick) / decision_count
                if decision_count
                else 0.0
            ),
            "candidates_per_tick": _summarize_values(candidate_count_per_tick),
            "selected_candidates_per_tick": _summarize_values(selected_candidate_count_per_tick),
            "decisions_per_tick": _summarize_values(decision_count_per_tick),
            "blocked_rate": (
                action_counter["BLOCKED_BY_SAFETY_GATE"] / decision_count
                if decision_count
                else 0.0
            ),
            "simulated_action_rate": (
                action_counter["SIMULATED_ACTION"] / decision_count
                if decision_count
                else 0.0
            ),
        },
    }
