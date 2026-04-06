from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from thesis3.dataclass_compat import dataclass, field
from thesis3.video_data import EventAnnotation


DEFAULT_ALERT_ACTION_STATES = {
    "REVIEW_REQUIRED",
    "SIMULATED_ACTION",
    "BLOCKED_BY_SAFETY_GATE",
}
DEFAULT_POSITIVE_EVENT_LABELS = {"bird_present"}
DEFAULT_NEGATIVE_EVENT_LABELS = {"bird_absent", "hard_negative"}
DEFAULT_IGNORED_EVENT_LABELS = {"unknown"}


@dataclass(slots=True)
class LoggedDecision:
    decision_id: str
    timestamp: float
    source_camera_id: str | None
    action_state: str
    policy_state: str
    track_id: str
    class_name: str | None = None
    reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EventGtMatch:
    annotation_id: str
    label: str
    camera_id: str
    start_time_s: float
    end_time_s: float
    outcome: str
    overlapped_decision_count: int
    overlapped_alert_count: int
    overlapped_action_counts: dict[str, int] = field(default_factory=dict)
    matched_decision_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EventGtEvaluationSummary:
    event_count: int
    positive_event_count: int
    negative_event_count: int
    ignored_event_count: int
    positive_hit_count: int
    positive_miss_count: int
    negative_clean_count: int
    negative_false_alert_count: int
    alert_decision_count: int
    unmatched_alert_decision_count: int
    per_event_matches: list[EventGtMatch] = field(default_factory=list)
    decision_action_counts: dict[str, int] = field(default_factory=dict)
    event_label_counts: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def evaluate_event_ground_truth(
    *,
    event_log_path: str | Path,
    events: list[EventAnnotation],
    overlap_tolerance_s: float = 0.0,
    alert_action_states: set[str] | None = None,
    positive_event_labels: set[str] | None = None,
    negative_event_labels: set[str] | None = None,
    ignored_event_labels: set[str] | None = None,
) -> EventGtEvaluationSummary:
    alert_action_states = alert_action_states or set(DEFAULT_ALERT_ACTION_STATES)
    positive_event_labels = positive_event_labels or set(DEFAULT_POSITIVE_EVENT_LABELS)
    negative_event_labels = negative_event_labels or set(DEFAULT_NEGATIVE_EVENT_LABELS)
    ignored_event_labels = ignored_event_labels or set(DEFAULT_IGNORED_EVENT_LABELS)

    decisions = load_logged_decisions(event_log_path)
    alert_decisions = [decision for decision in decisions if decision.action_state in alert_action_states]
    matched_alert_decision_ids: set[str] = set()
    per_event_matches: list[EventGtMatch] = []

    positive_hit_count = 0
    positive_miss_count = 0
    negative_clean_count = 0
    negative_false_alert_count = 0
    ignored_event_count = 0

    for event in events:
        label = event.label.value
        overlapped_decisions = [
            decision
            for decision in decisions
            if _decision_overlaps_event(
                decision=decision,
                event=event,
                overlap_tolerance_s=overlap_tolerance_s,
            )
        ]
        overlapped_alerts = [decision for decision in overlapped_decisions if decision.action_state in alert_action_states]
        matched_alert_decision_ids.update(decision.decision_id for decision in overlapped_alerts)
        action_counts = Counter(decision.action_state for decision in overlapped_decisions)

        if label in positive_event_labels:
            if overlapped_alerts:
                outcome = "hit"
                positive_hit_count += 1
            else:
                outcome = "miss"
                positive_miss_count += 1
        elif label in negative_event_labels:
            if overlapped_alerts:
                outcome = "false_alert"
                negative_false_alert_count += 1
            else:
                outcome = "clean"
                negative_clean_count += 1
        else:
            outcome = "ignored"
            ignored_event_count += 1

        per_event_matches.append(
            EventGtMatch(
                annotation_id=event.annotation_id,
                label=label,
                camera_id=event.camera_id,
                start_time_s=event.start_time_s,
                end_time_s=event.end_time_s,
                outcome=outcome,
                overlapped_decision_count=len(overlapped_decisions),
                overlapped_alert_count=len(overlapped_alerts),
                overlapped_action_counts=dict(sorted(action_counts.items())),
                matched_decision_ids=[decision.decision_id for decision in overlapped_decisions],
                metadata={
                    "quality_tags": list(event.quality_tags),
                    "annotator": event.annotator,
                },
            )
        )

    unmatched_alert_decision_count = sum(
        1 for decision in alert_decisions if decision.decision_id not in matched_alert_decision_ids
    )
    decision_action_counts = Counter(decision.action_state for decision in decisions)
    event_label_counts = Counter(event.label.value for event in events)

    positive_event_count = sum(1 for event in events if event.label.value in positive_event_labels)
    negative_event_count = sum(1 for event in events if event.label.value in negative_event_labels)

    return EventGtEvaluationSummary(
        event_count=len(events),
        positive_event_count=positive_event_count,
        negative_event_count=negative_event_count,
        ignored_event_count=ignored_event_count,
        positive_hit_count=positive_hit_count,
        positive_miss_count=positive_miss_count,
        negative_clean_count=negative_clean_count,
        negative_false_alert_count=negative_false_alert_count,
        alert_decision_count=len(alert_decisions),
        unmatched_alert_decision_count=unmatched_alert_decision_count,
        per_event_matches=per_event_matches,
        decision_action_counts=dict(sorted(decision_action_counts.items())),
        event_label_counts=dict(sorted(event_label_counts.items())),
        metadata={
            "event_log_path": str(event_log_path),
            "overlap_tolerance_s": overlap_tolerance_s,
            "alert_action_states": sorted(alert_action_states),
            "positive_event_labels": sorted(positive_event_labels),
            "negative_event_labels": sorted(negative_event_labels),
            "ignored_event_labels": sorted(ignored_event_labels),
        },
    )


def format_event_gt_evaluation(summary: EventGtEvaluationSummary) -> str:
    positive_recall = (
        summary.positive_hit_count / summary.positive_event_count if summary.positive_event_count else 0.0
    )
    negative_clean_rate = (
        summary.negative_clean_count / summary.negative_event_count if summary.negative_event_count else 0.0
    )
    lines = [
        f"event_count={summary.event_count}",
        f"positive_event_count={summary.positive_event_count}",
        f"negative_event_count={summary.negative_event_count}",
        f"ignored_event_count={summary.ignored_event_count}",
        f"positive_hit_count={summary.positive_hit_count}",
        f"positive_miss_count={summary.positive_miss_count}",
        f"negative_clean_count={summary.negative_clean_count}",
        f"negative_false_alert_count={summary.negative_false_alert_count}",
        f"alert_decision_count={summary.alert_decision_count}",
        f"unmatched_alert_decision_count={summary.unmatched_alert_decision_count}",
        f"positive_recall={positive_recall:.4f}",
        f"negative_clean_rate={negative_clean_rate:.4f}",
    ]
    if summary.decision_action_counts:
        lines.append(f"decision_action_counts={summary.decision_action_counts}")
    if summary.event_label_counts:
        lines.append(f"event_label_counts={summary.event_label_counts}")
    return "\n".join(lines)


def load_logged_decisions(event_log_path: str | Path) -> list[LoggedDecision]:
    decisions: list[LoggedDecision] = []
    path = Path(event_log_path)
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("event_type") != "decision_record":
            continue
        payload = record.get("payload", {})
        metadata = payload.get("metadata", {}) or {}
        timestamp = payload.get("timestamp")
        if timestamp is None:
            timestamp = record.get("timestamp")
        if timestamp is None:
            continue
        decisions.append(
            LoggedDecision(
                decision_id=f"{path.stem}-decision-{index:04d}",
                timestamp=float(timestamp),
                source_camera_id=metadata.get("source_camera_id"),
                action_state=str(payload.get("action_state")),
                policy_state=str(payload.get("policy_state")),
                track_id=str(payload.get("track_id")),
                class_name=(payload.get("stage1_summary") or {}).get("class_name"),
                reasons=[str(reason) for reason in payload.get("reasons", [])],
                metadata=dict(metadata),
            )
        )
    return decisions


def _decision_overlaps_event(
    *,
    decision: LoggedDecision,
    event: EventAnnotation,
    overlap_tolerance_s: float,
) -> bool:
    if decision.source_camera_id is not None and decision.source_camera_id != event.camera_id:
        return False
    start = event.start_time_s - overlap_tolerance_s
    end = event.end_time_s + overlap_tolerance_s
    return start <= decision.timestamp <= end
