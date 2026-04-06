from __future__ import annotations

from pathlib import Path
from typing import Any

from thesis3.dataclass_compat import dataclass, field
from thesis3.frame_gt_evaluation import FrameGtEvaluationSummary, evaluate_frame_ground_truth
from thesis3.gt_evaluation import EventGtEvaluationSummary, evaluate_event_ground_truth
from thesis3.tracking_gt_evaluation import TrackingGtEvaluationSummary, evaluate_tracking_ground_truth
from thesis3.verification_gt_evaluation import VerificationGtEvaluationSummary, evaluate_verification_ground_truth
from thesis3.video_data import EventAnnotation, FrameAnnotation


@dataclass(slots=True)
class GtEvalSuiteRecord:
    label: str
    event_log_path: str
    event_summary: EventGtEvaluationSummary | None = None
    frame_summary: FrameGtEvaluationSummary | None = None
    tracking_summary: TrackingGtEvaluationSummary | None = None
    verification_summary: VerificationGtEvaluationSummary | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class GtEvalSuiteSummary:
    record_count: int
    records: list[GtEvalSuiteRecord] = field(default_factory=list)
    matrix: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def run_gt_eval_suite(
    *,
    entries: list[tuple[str, str]],
    events: list[EventAnnotation] | None = None,
    frames: list[FrameAnnotation] | None = None,
    tracking_frames: list[FrameAnnotation] | None = None,
    verification_frames: list[FrameAnnotation] | None = None,
    event_overlap_tolerance_s: float = 0.0,
    frame_iou_threshold: float = 0.5,
    frame_timestamp_tolerance_s: float = 0.05,
    frame_class_agnostic: bool = False,
    tracking_timestamp_tolerance_s: float = 0.05,
    verification_iou_threshold: float = 0.1,
    verification_timestamp_tolerance_s: float = 0.05,
    verification_class_agnostic: bool = False,
) -> GtEvalSuiteSummary:
    records: list[GtEvalSuiteRecord] = []
    matrix: list[dict[str, Any]] = []
    for label, event_log_path in entries:
        event_summary = None
        frame_summary = None
        tracking_summary = None
        verification_summary = None
        if events:
            event_summary = evaluate_event_ground_truth(
                event_log_path=event_log_path,
                events=events,
                overlap_tolerance_s=event_overlap_tolerance_s,
            )
        if frames:
            frame_summary = evaluate_frame_ground_truth(
                event_log_path=event_log_path,
                frames=frames,
                iou_threshold=frame_iou_threshold,
                timestamp_tolerance_s=frame_timestamp_tolerance_s,
                class_agnostic=frame_class_agnostic,
            )
        if tracking_frames:
            tracking_summary = evaluate_tracking_ground_truth(
                event_log_path=event_log_path,
                frames=tracking_frames,
                timestamp_tolerance_s=tracking_timestamp_tolerance_s,
            )
        if verification_frames:
            verification_summary = evaluate_verification_ground_truth(
                event_log_path=event_log_path,
                frames=verification_frames,
                iou_threshold=verification_iou_threshold,
                timestamp_tolerance_s=verification_timestamp_tolerance_s,
                class_agnostic=verification_class_agnostic,
            )
        record = GtEvalSuiteRecord(
            label=label,
            event_log_path=str(event_log_path),
            event_summary=event_summary,
            frame_summary=frame_summary,
            tracking_summary=tracking_summary,
            verification_summary=verification_summary,
        )
        records.append(record)
        matrix.append(_record_to_matrix_row(record))

    return GtEvalSuiteSummary(
        record_count=len(records),
        records=records,
        matrix=matrix,
        metadata={
            "event_overlap_tolerance_s": event_overlap_tolerance_s,
            "frame_iou_threshold": frame_iou_threshold,
            "frame_timestamp_tolerance_s": frame_timestamp_tolerance_s,
            "frame_class_agnostic": frame_class_agnostic,
            "tracking_timestamp_tolerance_s": tracking_timestamp_tolerance_s,
            "verification_iou_threshold": verification_iou_threshold,
            "verification_timestamp_tolerance_s": verification_timestamp_tolerance_s,
            "verification_class_agnostic": verification_class_agnostic,
        },
    )


def format_gt_eval_suite(summary: GtEvalSuiteSummary) -> str:
    lines = [f"record_count={summary.record_count}"]
    for row in summary.matrix:
        lines.append(str(row))
    return "\n".join(lines)


def normalize_suite_entries(entries: list[str]) -> list[tuple[str, str]]:
    normalized: list[tuple[str, str]] = []
    for entry in entries:
        if "=" in entry:
            label, path = entry.split("=", 1)
        else:
            path = entry
            label = Path(entry).stem
        normalized.append((label, path))
    return normalized


def _record_to_matrix_row(record: GtEvalSuiteRecord) -> dict[str, Any]:
    row: dict[str, Any] = {
        "label": record.label,
        "event_log_path": record.event_log_path,
    }
    if record.event_summary is not None:
        row.update(
            {
                "event_positive_recall": (
                    record.event_summary.positive_hit_count / record.event_summary.positive_event_count
                    if record.event_summary.positive_event_count
                    else 0.0
                ),
                "event_negative_clean_rate": (
                    record.event_summary.negative_clean_count / record.event_summary.negative_event_count
                    if record.event_summary.negative_event_count
                    else 0.0
                ),
                "event_alert_decision_count": record.event_summary.alert_decision_count,
                "event_unmatched_alert_decision_count": record.event_summary.unmatched_alert_decision_count,
            }
        )
    if record.frame_summary is not None:
        row.update(
            {
                "frame_precision": record.frame_summary.precision,
                "frame_recall": record.frame_summary.recall,
                "frame_missing_observation_count": record.frame_summary.missing_observation_count,
                "frame_false_positive_count": record.frame_summary.false_positive_count,
                "frame_false_negative_count": record.frame_summary.false_negative_count,
            }
        )
    if record.verification_summary is not None:
        row.update(
            {
                "verification_acceptance_precision": record.verification_summary.acceptance_precision,
                "verification_positive_recall": record.verification_summary.positive_recall,
                "verification_rejection_specificity": record.verification_summary.rejection_specificity,
                "verification_missing_gt_count": record.verification_summary.missing_gt_count,
                "verification_false_accept_count": record.verification_summary.false_accept_count,
                "verification_false_reject_count": record.verification_summary.false_reject_count,
            }
        )
    if record.tracking_summary is not None:
        row.update(
            {
                "tracking_continuity_recall": record.tracking_summary.continuity_recall,
                "tracking_fragmentation_count": record.tracking_summary.object_fragmentation_count,
                "tracking_id_switch_count": record.tracking_summary.id_switch_count,
                "handoff_transition_count": record.tracking_summary.handoff_transition_count,
                "handoff_success_rate": record.tracking_summary.handoff_success_rate,
                "handoff_failure_count": record.tracking_summary.handoff_failure_count,
            }
        )
    return row
