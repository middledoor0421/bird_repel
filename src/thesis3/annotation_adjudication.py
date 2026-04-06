from __future__ import annotations

from collections import Counter
from typing import Any

from thesis3.dataclass_compat import dataclass, field
from thesis3.video_data import EventAnnotation, FrameAnnotation, write_jsonl


UNRESOLVED_ADJUDICATION_STATUSES = {"pending", "needs_second_review"}


@dataclass(slots=True)
class AdjudicationTask:
    task_id: str
    source_kind: str
    source_annotation_id: str
    asset_id: str
    camera_id: str
    source_path: str
    start_time_s: float
    end_time_s: float
    current_label: str
    adjudication_status: str
    required_action: str
    suggested_owner_role: str
    priority: int
    reason_tags: list[str] = field(default_factory=list)
    context_annotation_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AdjudicationTaskSummary:
    task_count: int
    source_kind_counts: dict[str, int] = field(default_factory=dict)
    status_counts: dict[str, int] = field(default_factory=dict)
    required_action_counts: dict[str, int] = field(default_factory=dict)
    owner_role_counts: dict[str, int] = field(default_factory=dict)
    reason_tag_counts: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def build_adjudication_tasks(
    *,
    events: list[EventAnnotation] | None = None,
    frames: list[FrameAnnotation] | None = None,
) -> list[AdjudicationTask]:
    events = events or []
    frames = frames or []

    tasks: list[AdjudicationTask] = []
    for event in events:
        task = _build_event_adjudication_task(event)
        if task is not None:
            tasks.append(task)
    for frame in frames:
        task = _build_frame_adjudication_task(frame)
        if task is not None:
            tasks.append(task)
    return sorted(tasks, key=lambda task: (-task.priority, task.start_time_s, task.task_id))


def summarize_adjudication_tasks(tasks: list[AdjudicationTask]) -> AdjudicationTaskSummary:
    source_kind_counts = Counter(task.source_kind for task in tasks)
    status_counts = Counter(task.adjudication_status for task in tasks)
    required_action_counts = Counter(task.required_action for task in tasks)
    owner_role_counts = Counter(task.suggested_owner_role for task in tasks)
    reason_tag_counts = Counter()
    for task in tasks:
        reason_tag_counts.update(task.reason_tags)

    return AdjudicationTaskSummary(
        task_count=len(tasks),
        source_kind_counts=dict(sorted(source_kind_counts.items())),
        status_counts=dict(sorted(status_counts.items())),
        required_action_counts=dict(sorted(required_action_counts.items())),
        owner_role_counts=dict(sorted(owner_role_counts.items())),
        reason_tag_counts=dict(sorted(reason_tag_counts.items())),
        metadata={
            "unresolved_adjudication_statuses": sorted(UNRESOLVED_ADJUDICATION_STATUSES),
        },
    )


def format_adjudication_task_summary(summary: AdjudicationTaskSummary) -> str:
    lines = [f"task_count={summary.task_count}"]
    if summary.source_kind_counts:
        lines.append(f"source_kind_counts={summary.source_kind_counts}")
    if summary.status_counts:
        lines.append(f"status_counts={summary.status_counts}")
    if summary.required_action_counts:
        lines.append(f"required_action_counts={summary.required_action_counts}")
    if summary.owner_role_counts:
        lines.append(f"owner_role_counts={summary.owner_role_counts}")
    if summary.reason_tag_counts:
        lines.append(f"reason_tag_counts={summary.reason_tag_counts}")
    return "\n".join(lines)


def export_adjudication_tasks(tasks: list[AdjudicationTask], output_path: str) -> None:
    write_jsonl(tasks, output_path)


def _build_event_adjudication_task(event: EventAnnotation) -> AdjudicationTask | None:
    ambiguity_reasons = _extract_metadata_list(event.metadata, "ambiguity_reasons", "ambiguity_reason")
    status = _resolve_status(
        explicit_status=_extract_metadata_string(event.metadata, "adjudication_status"),
        is_unknown=event.label.value == "unknown",
    )
    if status not in UNRESOLVED_ADJUDICATION_STATUSES and event.label.value != "unknown":
        return None

    required_action, owner_role = _resolve_workflow(status)
    reason_tags = list(ambiguity_reasons)
    if event.label.value == "unknown":
        reason_tags.append("unknown_label")
    if not reason_tags:
        reason_tags.append("manual_review")
    priority = _compute_priority(status=status, reason_tags=reason_tags)
    return AdjudicationTask(
        task_id=f"adj-event-{event.annotation_id}",
        source_kind="event",
        source_annotation_id=event.annotation_id,
        asset_id=event.asset_id,
        camera_id=event.camera_id,
        source_path=event.source_path,
        start_time_s=event.start_time_s,
        end_time_s=event.end_time_s,
        current_label=event.label.value,
        adjudication_status=status,
        required_action=required_action,
        suggested_owner_role=owner_role,
        priority=priority,
        reason_tags=sorted(set(reason_tags)),
        metadata={
            "annotator": event.annotator,
            "notes": event.notes,
        },
    )


def _build_frame_adjudication_task(frame: FrameAnnotation) -> AdjudicationTask | None:
    ambiguity_reasons = _extract_metadata_list(frame.metadata, "ambiguity_reasons", "ambiguity_reason")
    has_unknown_object = any(obj.class_name == "unknown" for obj in frame.objects)
    status = _resolve_status(
        explicit_status=_extract_metadata_string(frame.metadata, "adjudication_status"),
        is_unknown=has_unknown_object,
    )
    if status not in UNRESOLVED_ADJUDICATION_STATUSES and not has_unknown_object:
        return None

    required_action, owner_role = _resolve_workflow(status)
    reason_tags = list(ambiguity_reasons)
    if has_unknown_object:
        reason_tags.append("unknown_object")
    if not reason_tags:
        reason_tags.append("manual_review")
    priority = _compute_priority(status=status, reason_tags=reason_tags)
    context_annotation_ids: list[str] = []
    if frame.source_event_annotation_id:
        context_annotation_ids.append(frame.source_event_annotation_id)
    return AdjudicationTask(
        task_id=f"adj-frame-{frame.annotation_id}",
        source_kind="frame",
        source_annotation_id=frame.annotation_id,
        asset_id=frame.asset_id,
        camera_id=frame.camera_id,
        source_path=frame.source_path,
        start_time_s=frame.timestamp_s,
        end_time_s=frame.timestamp_s,
        current_label="unknown" if has_unknown_object else "frame_review",
        adjudication_status=status,
        required_action=required_action,
        suggested_owner_role=owner_role,
        priority=priority,
        reason_tags=sorted(set(reason_tags)),
        context_annotation_ids=context_annotation_ids,
        metadata={
            "annotator": frame.annotator,
            "notes": frame.notes,
        },
    )


def _resolve_status(*, explicit_status: str | None, is_unknown: bool) -> str:
    if explicit_status:
        return explicit_status
    if is_unknown:
        return "pending"
    return "resolved"


def _resolve_workflow(status: str) -> tuple[str, str]:
    if status == "needs_second_review":
        return "second_review", "secondary_reviewer"
    if status == "waived":
        return "waive_or_archive", "annotation_lead"
    if status == "resolved":
        return "record_resolution", "annotation_lead"
    return "primary_review", "primary_annotator"


def _compute_priority(*, status: str, reason_tags: list[str]) -> int:
    priority = 50
    if status == "needs_second_review":
        priority += 30
    elif status == "pending":
        priority += 10
    if "unknown_label" in reason_tags or "unknown_object" in reason_tags:
        priority += 10
    if {"severe_glare", "conflicting_cues"} & set(reason_tags):
        priority += 5
    return priority


def _extract_metadata_list(metadata: dict[str, Any], primary_key: str, fallback_key: str | None = None) -> list[str]:
    values = metadata.get(primary_key)
    if values is None and fallback_key is not None:
        values = metadata.get(fallback_key)
    if values is None:
        return []
    if isinstance(values, str):
        return [values]
    if isinstance(values, list):
        return [str(value) for value in values if value is not None]
    return [str(values)]


def _extract_metadata_string(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    return str(value)
