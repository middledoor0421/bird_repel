from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from thesis3.dataclass_compat import dataclass, field
from thesis3.video_data import EventAnnotation, FrameAnnotation, VideoAsset


DEFAULT_ANNOTATION_VOCABULARY = {
    "event_quality_tags": [
        "clear",
        "blur",
        "motion_blur",
        "glare",
        "reflection",
        "night",
        "low_light",
        "background_motion",
        "distant_object",
        "partial_visibility",
        "occlusion",
        "shadow",
        "clutter",
        "small_object",
        "hard_negative",
        "rain",
    ],
    "frame_object_tags": [
        "small_object",
        "partial_visibility",
        "occluded",
        "boundary_touching",
        "blur",
        "glare",
        "truncated",
    ],
    "visibility_values": [
        "clear",
        "partial",
        "occluded",
        "tiny",
        "blurred",
    ],
    "class_names": [
        "bird",
        "target",
        "distractor",
        "unknown",
    ],
    "ambiguity_reasons": [
        "too_small",
        "too_blurry",
        "severe_glare",
        "occluded",
        "distant_motion",
        "uncertain_species",
        "conflicting_cues",
        "insufficient_context",
    ],
    "adjudication_statuses": [
        "pending",
        "needs_second_review",
        "resolved",
        "waived",
    ],
}


@dataclass(slots=True)
class AnnotationFinding:
    severity: str
    code: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AnnotationValidationReport:
    event_annotation_count: int
    frame_annotation_count: int
    error_count: int
    warning_count: int
    findings: list[AnnotationFinding] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def load_annotation_vocabulary(path: str | Path | None = None) -> dict[str, set[str]]:
    raw = dict(DEFAULT_ANNOTATION_VOCABULARY)
    if path is not None:
        loaded = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("Annotation vocabulary file must be a JSON object.")
        raw.update(loaded)
    return {
        key: {str(value) for value in values}
        for key, values in raw.items()
        if isinstance(values, list)
    }


def validate_annotations(
    *,
    events: list[EventAnnotation] | None = None,
    frames: list[FrameAnnotation] | None = None,
    assets_by_id: dict[str, VideoAsset] | None = None,
    vocabulary: dict[str, set[str]] | None = None,
) -> AnnotationValidationReport:
    events = events or []
    frames = frames or []
    assets_by_id = assets_by_id or {}
    vocabulary = vocabulary or load_annotation_vocabulary()
    findings: list[AnnotationFinding] = []
    events_by_id = {event.annotation_id: event for event in events}

    for event in events:
        findings.extend(_validate_event(event, assets_by_id, vocabulary))

    for frame in frames:
        findings.extend(_validate_frame(frame, assets_by_id, events_by_id, vocabulary))

    error_count = sum(1 for finding in findings if finding.severity == "error")
    warning_count = sum(1 for finding in findings if finding.severity == "warning")
    return AnnotationValidationReport(
        event_annotation_count=len(events),
        frame_annotation_count=len(frames),
        error_count=error_count,
        warning_count=warning_count,
        findings=findings,
        metadata={
            "vocabulary": {key: sorted(values) for key, values in vocabulary.items()},
        },
    )


def format_annotation_validation_report(report: AnnotationValidationReport) -> str:
    lines = [
        f"event_annotation_count={report.event_annotation_count}",
        f"frame_annotation_count={report.frame_annotation_count}",
        f"error_count={report.error_count}",
        f"warning_count={report.warning_count}",
    ]
    if report.findings:
        top_codes: dict[str, int] = {}
        for finding in report.findings:
            top_codes[finding.code] = top_codes.get(finding.code, 0) + 1
        lines.append(f"finding_codes={json.dumps(top_codes, ensure_ascii=True, sort_keys=True)}")
    return "\n".join(lines)


def _validate_event(
    event: EventAnnotation,
    assets_by_id: dict[str, VideoAsset],
    vocabulary: dict[str, set[str]],
) -> list[AnnotationFinding]:
    findings: list[AnnotationFinding] = []
    ambiguity_reasons = _extract_metadata_list(event.metadata, "ambiguity_reasons", "ambiguity_reason")
    adjudication_status = _extract_metadata_string(event.metadata, "adjudication_status")
    findings.extend(
        _validate_tags(
            raw_tags=ambiguity_reasons,
            allowed_tags=vocabulary.get("ambiguity_reasons", set()),
            severity="warning",
            code="unknown_ambiguity_reason",
            context={"annotation_id": event.annotation_id},
        )
    )
    if adjudication_status is not None:
        findings.extend(
            _validate_tags(
                raw_tags=[adjudication_status],
                allowed_tags=vocabulary.get("adjudication_statuses", set()),
                severity="warning",
                code="unknown_adjudication_status",
                context={"annotation_id": event.annotation_id},
            )
        )

    if event.start_time_s < 0.0 or event.end_time_s < 0.0:
        findings.append(
            AnnotationFinding(
                severity="error",
                code="negative_event_timestamp",
                message="Event annotation has a negative timestamp.",
                context={"annotation_id": event.annotation_id},
            )
        )
    if event.end_time_s < event.start_time_s:
        findings.append(
            AnnotationFinding(
                severity="error",
                code="event_time_inversion",
                message="Event annotation end_time_s is earlier than start_time_s.",
                context={
                    "annotation_id": event.annotation_id,
                    "start_time_s": event.start_time_s,
                    "end_time_s": event.end_time_s,
                },
            )
        )

    if event.bird_count_min is not None and event.bird_count_min < 0:
        findings.append(
            AnnotationFinding(
                severity="error",
                code="negative_bird_count_min",
                message="bird_count_min must not be negative.",
                context={"annotation_id": event.annotation_id},
            )
        )
    if event.bird_count_max is not None and event.bird_count_max < 0:
        findings.append(
            AnnotationFinding(
                severity="error",
                code="negative_bird_count_max",
                message="bird_count_max must not be negative.",
                context={"annotation_id": event.annotation_id},
            )
        )
    if event.bird_count_min is not None and event.bird_count_max is not None:
        if event.bird_count_max < event.bird_count_min:
            findings.append(
                AnnotationFinding(
                    severity="error",
                    code="bird_count_range_inversion",
                    message="bird_count_max is smaller than bird_count_min.",
                    context={"annotation_id": event.annotation_id},
                )
            )

    if event.label.value == "bird_present":
        if event.bird_count_max is not None and event.bird_count_max <= 0:
            findings.append(
                AnnotationFinding(
                    severity="warning",
                    code="positive_zero_bird_count",
                    message="bird_present event has non-positive bird_count_max.",
                    context={"annotation_id": event.annotation_id},
                )
            )
    elif event.label.value in {"bird_absent", "hard_negative"}:
        for count_field, count_value in (
            ("bird_count_min", event.bird_count_min),
            ("bird_count_max", event.bird_count_max),
        ):
            if count_value not in {None, 0}:
                findings.append(
                    AnnotationFinding(
                        severity="warning",
                        code="negative_nonzero_bird_count",
                        message=f"{event.label.value} event has non-zero {count_field}.",
                        context={"annotation_id": event.annotation_id, count_field: count_value},
                    )
                )
    elif event.label.value == "unknown":
        if not ambiguity_reasons:
            findings.append(
                AnnotationFinding(
                    severity="warning",
                    code="unknown_without_ambiguity_reason",
                    message="unknown event should record at least one ambiguity reason in metadata.",
                    context={"annotation_id": event.annotation_id},
                )
            )
        if adjudication_status is None:
            findings.append(
                AnnotationFinding(
                    severity="warning",
                    code="unknown_without_adjudication_status",
                    message="unknown event should record adjudication_status in metadata.",
                    context={"annotation_id": event.annotation_id},
                )
            )
        for count_field, count_value in (
            ("bird_count_min", event.bird_count_min),
            ("bird_count_max", event.bird_count_max),
        ):
            if count_value not in {None, 0}:
                findings.append(
                    AnnotationFinding(
                        severity="warning",
                        code="unknown_nonzero_bird_count",
                        message=f"unknown event has non-zero {count_field}.",
                        context={"annotation_id": event.annotation_id, count_field: count_value},
                    )
                )
    if event.label.value != "unknown" and adjudication_status in {"pending", "needs_second_review"}:
        findings.append(
            AnnotationFinding(
                severity="warning",
                code="final_label_pending_adjudication",
                message="Final event label still carries a pending adjudication status.",
                context={
                    "annotation_id": event.annotation_id,
                    "label": event.label.value,
                    "adjudication_status": adjudication_status,
                },
            )
        )

    findings.extend(
        _validate_tags(
            raw_tags=event.quality_tags,
            allowed_tags=vocabulary.get("event_quality_tags", set()),
            severity="warning",
            code="unknown_event_quality_tag",
            context={"annotation_id": event.annotation_id},
        )
    )

    asset = assets_by_id.get(event.asset_id)
    if asset is None:
        findings.append(
            AnnotationFinding(
                severity="warning",
                code="missing_asset_for_event",
                message="Event annotation asset_id is missing from the provided video index.",
                context={"annotation_id": event.annotation_id, "asset_id": event.asset_id},
            )
        )
    else:
        if asset.camera_id != event.camera_id:
            findings.append(
                AnnotationFinding(
                    severity="error",
                    code="event_camera_mismatch",
                    message="Event annotation camera_id does not match indexed asset camera_id.",
                    context={
                        "annotation_id": event.annotation_id,
                        "event_camera_id": event.camera_id,
                        "asset_camera_id": asset.camera_id,
                    },
                )
            )
        if asset.source_path != event.source_path:
            findings.append(
                AnnotationFinding(
                    severity="warning",
                    code="event_source_path_mismatch",
                    message="Event annotation source_path does not match indexed asset source_path.",
                    context={"annotation_id": event.annotation_id},
                )
            )
        if event.end_time_s > asset.duration_s + 1e-6:
            findings.append(
                AnnotationFinding(
                    severity="warning",
                    code="event_outside_asset_duration",
                    message="Event annotation extends beyond indexed asset duration.",
                    context={
                        "annotation_id": event.annotation_id,
                        "asset_duration_s": asset.duration_s,
                        "end_time_s": event.end_time_s,
                    },
                )
            )
    return findings


def _validate_frame(
    frame: FrameAnnotation,
    assets_by_id: dict[str, VideoAsset],
    events_by_id: dict[str, EventAnnotation],
    vocabulary: dict[str, set[str]],
) -> list[AnnotationFinding]:
    findings: list[AnnotationFinding] = []
    ambiguity_reasons = _extract_metadata_list(frame.metadata, "ambiguity_reasons", "ambiguity_reason")
    adjudication_status = _extract_metadata_string(frame.metadata, "adjudication_status")
    findings.extend(
        _validate_tags(
            raw_tags=ambiguity_reasons,
            allowed_tags=vocabulary.get("ambiguity_reasons", set()),
            severity="warning",
            code="unknown_frame_ambiguity_reason",
            context={"annotation_id": frame.annotation_id},
        )
    )
    if adjudication_status is not None:
        findings.extend(
            _validate_tags(
                raw_tags=[adjudication_status],
                allowed_tags=vocabulary.get("adjudication_statuses", set()),
                severity="warning",
                code="unknown_frame_adjudication_status",
                context={"annotation_id": frame.annotation_id},
            )
        )

    if frame.timestamp_s < 0.0:
        findings.append(
            AnnotationFinding(
                severity="error",
                code="negative_frame_timestamp",
                message="Frame annotation has a negative timestamp.",
                context={"annotation_id": frame.annotation_id},
            )
        )
    if not frame.objects:
        findings.append(
            AnnotationFinding(
                severity="warning",
                code="empty_frame_objects",
                message="Frame annotation has no objects.",
                context={"annotation_id": frame.annotation_id},
            )
        )

    asset = assets_by_id.get(frame.asset_id)
    if asset is None:
        findings.append(
            AnnotationFinding(
                severity="warning",
                code="missing_asset_for_frame",
                message="Frame annotation asset_id is missing from the provided video index.",
                context={"annotation_id": frame.annotation_id, "asset_id": frame.asset_id},
            )
        )
        asset_width = None
        asset_height = None
    else:
        asset_width = asset.width
        asset_height = asset.height
        if asset.camera_id != frame.camera_id:
            findings.append(
                AnnotationFinding(
                    severity="error",
                    code="frame_camera_mismatch",
                    message="Frame annotation camera_id does not match indexed asset camera_id.",
                    context={
                        "annotation_id": frame.annotation_id,
                        "frame_camera_id": frame.camera_id,
                        "asset_camera_id": asset.camera_id,
                    },
                )
            )
        if frame.timestamp_s > asset.duration_s + 1e-6:
            findings.append(
                AnnotationFinding(
                    severity="warning",
                    code="frame_outside_asset_duration",
                    message="Frame annotation timestamp exceeds indexed asset duration.",
                    context={"annotation_id": frame.annotation_id, "asset_duration_s": asset.duration_s},
                )
            )

    if frame.source_event_annotation_id:
        source_event = events_by_id.get(frame.source_event_annotation_id)
        if source_event is None:
            findings.append(
                AnnotationFinding(
                    severity="warning",
                    code="missing_source_event",
                    message="Frame annotation references a missing event annotation.",
                    context={
                        "annotation_id": frame.annotation_id,
                        "source_event_annotation_id": frame.source_event_annotation_id,
                    },
                )
            )
        else:
            if not (source_event.start_time_s - 1e-6 <= frame.timestamp_s <= source_event.end_time_s + 1e-6):
                findings.append(
                    AnnotationFinding(
                        severity="warning",
                        code="frame_outside_source_event",
                        message="Frame annotation timestamp is outside the referenced event time range.",
                        context={
                            "annotation_id": frame.annotation_id,
                            "source_event_annotation_id": source_event.annotation_id,
                        },
                    )
                )

    allowed_classes = vocabulary.get("class_names", set())
    allowed_visibility = vocabulary.get("visibility_values", set())
    allowed_object_tags = vocabulary.get("frame_object_tags", set())
    for index, obj in enumerate(frame.objects):
        if allowed_classes and obj.class_name not in allowed_classes:
            findings.append(
                AnnotationFinding(
                    severity="warning",
                    code="unknown_frame_class_name",
                    message="Frame annotation object class_name is not in the current vocabulary.",
                    context={"annotation_id": frame.annotation_id, "object_index": index, "class_name": obj.class_name},
                )
            )
        if obj.visibility is not None and allowed_visibility and obj.visibility not in allowed_visibility:
            findings.append(
                AnnotationFinding(
                    severity="warning",
                    code="unknown_visibility_value",
                    message="Frame annotation object visibility is not in the current vocabulary.",
                    context={"annotation_id": frame.annotation_id, "object_index": index, "visibility": obj.visibility},
                )
            )
        findings.extend(
            _validate_tags(
                raw_tags=obj.tags,
                allowed_tags=allowed_object_tags,
                severity="warning",
                code="unknown_frame_object_tag",
                context={"annotation_id": frame.annotation_id, "object_index": index},
            )
        )
        if obj.class_name == "unknown" and not ambiguity_reasons:
            findings.append(
                AnnotationFinding(
                    severity="warning",
                    code="unknown_frame_object_without_ambiguity_reason",
                    message="Frame annotation with unknown object class should record ambiguity reason metadata.",
                    context={"annotation_id": frame.annotation_id, "object_index": index},
                )
            )

        bbox = obj.bbox
        if bbox.x2 <= bbox.x1 or bbox.y2 <= bbox.y1:
            findings.append(
                AnnotationFinding(
                    severity="error",
                    code="invalid_bbox_extent",
                    message="Frame annotation bbox must have positive width and height.",
                    context={"annotation_id": frame.annotation_id, "object_index": index},
                )
            )
        if asset_width is not None and asset_height is not None:
            if bbox.x1 < 0 or bbox.y1 < 0 or bbox.x2 > asset_width or bbox.y2 > asset_height:
                findings.append(
                    AnnotationFinding(
                        severity="warning",
                        code="bbox_outside_frame",
                        message="Frame annotation bbox extends outside the indexed asset dimensions.",
                        context={
                            "annotation_id": frame.annotation_id,
                            "object_index": index,
                            "asset_width": asset_width,
                            "asset_height": asset_height,
                        },
                    )
                )

    return findings


def _validate_tags(
    *,
    raw_tags: list[str],
    allowed_tags: set[str],
    severity: str,
    code: str,
    context: dict[str, Any],
) -> list[AnnotationFinding]:
    findings: list[AnnotationFinding] = []
    for tag in raw_tags:
        if allowed_tags and tag not in allowed_tags:
            findings.append(
                AnnotationFinding(
                    severity=severity,
                    code=code,
                    message=f"Unknown tag: {tag}",
                    context={**context, "tag": tag},
                )
            )
    return findings


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
