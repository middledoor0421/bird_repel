from __future__ import annotations

from collections import Counter
from typing import Any

from thesis3.dataclass_compat import dataclass, field
from thesis3.video_data import EventAnnotation, FrameAnnotation


UNRESOLVED_ADJUDICATION_STATUSES = {"pending", "needs_second_review"}


@dataclass(slots=True)
class AnnotationQueueSummary:
    event_annotation_count: int
    frame_annotation_count: int
    unresolved_event_count: int
    unresolved_frame_count: int
    event_label_counts: dict[str, int] = field(default_factory=dict)
    event_adjudication_status_counts: dict[str, int] = field(default_factory=dict)
    frame_adjudication_status_counts: dict[str, int] = field(default_factory=dict)
    ambiguity_reason_counts: dict[str, int] = field(default_factory=dict)
    annotator_counts: dict[str, int] = field(default_factory=dict)
    unresolved_event_ids: list[str] = field(default_factory=list)
    unresolved_frame_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def summarize_annotation_queue(
    *,
    events: list[EventAnnotation] | None = None,
    frames: list[FrameAnnotation] | None = None,
) -> AnnotationQueueSummary:
    events = events or []
    frames = frames or []

    event_label_counts = Counter(event.label.value for event in events)
    event_adjudication_status_counts = Counter()
    frame_adjudication_status_counts = Counter()
    ambiguity_reason_counts = Counter()
    annotator_counts = Counter()
    unresolved_event_ids: list[str] = []
    unresolved_frame_ids: list[str] = []

    for event in events:
        if event.annotator:
            annotator_counts[event.annotator] += 1
        status = _extract_metadata_string(event.metadata, "adjudication_status")
        if status is not None:
            event_adjudication_status_counts[status] += 1
        reasons = _extract_metadata_list(event.metadata, "ambiguity_reasons", "ambiguity_reason")
        ambiguity_reason_counts.update(reasons)
        if event.label.value == "unknown" or status in UNRESOLVED_ADJUDICATION_STATUSES:
            unresolved_event_ids.append(event.annotation_id)

    for frame in frames:
        if frame.annotator:
            annotator_counts[frame.annotator] += 1
        status = _extract_metadata_string(frame.metadata, "adjudication_status")
        if status is not None:
            frame_adjudication_status_counts[status] += 1
        reasons = _extract_metadata_list(frame.metadata, "ambiguity_reasons", "ambiguity_reason")
        ambiguity_reason_counts.update(reasons)
        has_unknown_object = any(obj.class_name == "unknown" for obj in frame.objects)
        if has_unknown_object or status in UNRESOLVED_ADJUDICATION_STATUSES:
            unresolved_frame_ids.append(frame.annotation_id)

    return AnnotationQueueSummary(
        event_annotation_count=len(events),
        frame_annotation_count=len(frames),
        unresolved_event_count=len(unresolved_event_ids),
        unresolved_frame_count=len(unresolved_frame_ids),
        event_label_counts=dict(sorted(event_label_counts.items())),
        event_adjudication_status_counts=dict(sorted(event_adjudication_status_counts.items())),
        frame_adjudication_status_counts=dict(sorted(frame_adjudication_status_counts.items())),
        ambiguity_reason_counts=dict(sorted(ambiguity_reason_counts.items())),
        annotator_counts=dict(sorted(annotator_counts.items())),
        unresolved_event_ids=sorted(unresolved_event_ids),
        unresolved_frame_ids=sorted(unresolved_frame_ids),
        metadata={
            "unresolved_adjudication_statuses": sorted(UNRESOLVED_ADJUDICATION_STATUSES),
        },
    )


def format_annotation_queue_summary(summary: AnnotationQueueSummary) -> str:
    lines = [
        f"event_annotation_count={summary.event_annotation_count}",
        f"frame_annotation_count={summary.frame_annotation_count}",
        f"unresolved_event_count={summary.unresolved_event_count}",
        f"unresolved_frame_count={summary.unresolved_frame_count}",
    ]
    if summary.event_label_counts:
        lines.append(f"event_label_counts={summary.event_label_counts}")
    if summary.event_adjudication_status_counts:
        lines.append(f"event_adjudication_status_counts={summary.event_adjudication_status_counts}")
    if summary.frame_adjudication_status_counts:
        lines.append(f"frame_adjudication_status_counts={summary.frame_adjudication_status_counts}")
    if summary.ambiguity_reason_counts:
        lines.append(f"ambiguity_reason_counts={summary.ambiguity_reason_counts}")
    return "\n".join(lines)


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
