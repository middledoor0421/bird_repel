from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from thesis3.core import BBox
from thesis3.dataclass_compat import dataclass, field
from thesis3.frame_gt_evaluation import compute_iou
from thesis3.video_data import FrameAnnotation


DEFAULT_IGNORED_GT_CLASS_NAMES = {"unknown"}


@dataclass(slots=True)
class LoggedVerificationAttempt:
    request_id: str
    source_timestamp_s: float | None
    target_timestamp_s: float | None
    source_camera_id: str | None
    target_camera_id: str | None
    request_bbox: BBox | None
    supporting_bbox: BBox | None
    requested_class_name: str | None
    verified: bool
    verifier_score: float
    failure_reason: str | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class VerificationGtMatch:
    request_id: str
    camera_id: str | None
    timestamp_s: float | None
    frame_annotation_id: str | None
    outcome: str
    gt_positive: bool | None
    verified: bool
    matched_gt_count: int
    max_iou: float | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class VerificationGtEvaluationSummary:
    attempt_count: int
    evaluated_attempt_count: int
    missing_gt_count: int
    true_accept_count: int
    false_accept_count: int
    false_reject_count: int
    true_reject_count: int
    acceptance_precision: float
    positive_recall: float
    rejection_specificity: float
    per_attempt_matches: list[VerificationGtMatch] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def evaluate_verification_ground_truth(
    *,
    event_log_path: str | Path,
    frames: list[FrameAnnotation],
    iou_threshold: float = 0.1,
    timestamp_tolerance_s: float = 0.05,
    class_agnostic: bool = False,
    ignored_gt_class_names: set[str] | None = None,
) -> VerificationGtEvaluationSummary:
    ignored_gt_class_names = ignored_gt_class_names or set(DEFAULT_IGNORED_GT_CLASS_NAMES)
    attempts = load_verification_attempts(event_log_path)
    per_attempt_matches: list[VerificationGtMatch] = []

    true_accept_count = 0
    false_accept_count = 0
    false_reject_count = 0
    true_reject_count = 0
    missing_gt_count = 0
    evaluated_attempt_count = 0

    for attempt in attempts:
        if attempt.target_camera_id is None or attempt.target_timestamp_s is None:
            missing_gt_count += 1
            per_attempt_matches.append(
                VerificationGtMatch(
                    request_id=attempt.request_id,
                    camera_id=attempt.target_camera_id,
                    timestamp_s=attempt.target_timestamp_s,
                    frame_annotation_id=None,
                    outcome="missing_gt",
                    gt_positive=None,
                    verified=attempt.verified,
                    matched_gt_count=0,
                    max_iou=None,
                    metadata={"reason": "missing_target_camera_or_timestamp"},
                )
            )
            continue

        frame = _find_best_frame_annotation(
            frames=frames,
            camera_id=attempt.target_camera_id,
            timestamp_s=attempt.target_timestamp_s,
            timestamp_tolerance_s=timestamp_tolerance_s,
        )
        if frame is None:
            missing_gt_count += 1
            per_attempt_matches.append(
                VerificationGtMatch(
                    request_id=attempt.request_id,
                    camera_id=attempt.target_camera_id,
                    timestamp_s=attempt.target_timestamp_s,
                    frame_annotation_id=None,
                    outcome="missing_gt",
                    gt_positive=None,
                    verified=attempt.verified,
                    matched_gt_count=0,
                    max_iou=None,
                    metadata={"reason": "no_matching_frame_annotation"},
                )
            )
            continue

        evaluated_attempt_count += 1
        reference_bbox = attempt.supporting_bbox or attempt.request_bbox
        gt_objects = [obj for obj in frame.objects if obj.class_name not in ignored_gt_class_names]
        matching_ious: list[float] = []
        for obj in gt_objects:
            if reference_bbox is None:
                if class_agnostic or attempt.requested_class_name is None or obj.class_name == attempt.requested_class_name:
                    matching_ious.append(1.0)
                continue
            if not class_agnostic and attempt.requested_class_name is not None and obj.class_name != attempt.requested_class_name:
                continue
            matching_ious.append(compute_iou(obj.bbox, reference_bbox))
        matched_ious = [iou for iou in matching_ious if iou >= iou_threshold]
        gt_positive = bool(matched_ious)
        max_iou = max(matching_ious) if matching_ious else None

        if attempt.verified and gt_positive:
            outcome = "true_accept"
            true_accept_count += 1
        elif attempt.verified and not gt_positive:
            outcome = "false_accept"
            false_accept_count += 1
        elif (not attempt.verified) and gt_positive:
            outcome = "false_reject"
            false_reject_count += 1
        else:
            outcome = "true_reject"
            true_reject_count += 1

        per_attempt_matches.append(
            VerificationGtMatch(
                request_id=attempt.request_id,
                camera_id=attempt.target_camera_id,
                timestamp_s=attempt.target_timestamp_s,
                frame_annotation_id=frame.annotation_id,
                outcome=outcome,
                gt_positive=gt_positive,
                verified=attempt.verified,
                matched_gt_count=len(matched_ious),
                max_iou=max_iou,
                metadata={
                    "requested_class_name": attempt.requested_class_name,
                    "failure_reason": attempt.failure_reason,
                    "verifier_score": attempt.verifier_score,
                    "frame_notes": frame.notes,
                },
            )
        )

    acceptance_precision = (
        true_accept_count / (true_accept_count + false_accept_count)
        if (true_accept_count + false_accept_count)
        else 0.0
    )
    positive_recall = (
        true_accept_count / (true_accept_count + false_reject_count)
        if (true_accept_count + false_reject_count)
        else 0.0
    )
    rejection_specificity = (
        true_reject_count / (true_reject_count + false_accept_count)
        if (true_reject_count + false_accept_count)
        else 0.0
    )

    return VerificationGtEvaluationSummary(
        attempt_count=len(attempts),
        evaluated_attempt_count=evaluated_attempt_count,
        missing_gt_count=missing_gt_count,
        true_accept_count=true_accept_count,
        false_accept_count=false_accept_count,
        false_reject_count=false_reject_count,
        true_reject_count=true_reject_count,
        acceptance_precision=acceptance_precision,
        positive_recall=positive_recall,
        rejection_specificity=rejection_specificity,
        per_attempt_matches=per_attempt_matches,
        metadata={
            "event_log_path": str(event_log_path),
            "iou_threshold": iou_threshold,
            "timestamp_tolerance_s": timestamp_tolerance_s,
            "class_agnostic": class_agnostic,
            "ignored_gt_class_names": sorted(ignored_gt_class_names),
        },
    )


def format_verification_gt_evaluation(summary: VerificationGtEvaluationSummary) -> str:
    lines = [
        f"attempt_count={summary.attempt_count}",
        f"evaluated_attempt_count={summary.evaluated_attempt_count}",
        f"missing_gt_count={summary.missing_gt_count}",
        f"true_accept_count={summary.true_accept_count}",
        f"false_accept_count={summary.false_accept_count}",
        f"false_reject_count={summary.false_reject_count}",
        f"true_reject_count={summary.true_reject_count}",
        f"acceptance_precision={summary.acceptance_precision:.4f}",
        f"positive_recall={summary.positive_recall:.4f}",
        f"rejection_specificity={summary.rejection_specificity:.4f}",
    ]
    return "\n".join(lines)


def load_verification_attempts(event_log_path: str | Path) -> list[LoggedVerificationAttempt]:
    path = Path(event_log_path)
    pending_requests: dict[str, dict[str, Any]] = {}
    attempts: list[LoggedVerificationAttempt] = []

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        event_type = record.get("event_type")
        payload = record.get("payload", {})
        if event_type == "verification_request":
            pending_requests[str(payload["request_id"])] = {
                "source_timestamp_s": record.get("timestamp"),
                "source_camera_id": payload.get("source_camera_id"),
                "target_camera_id": payload.get("target_camera_id"),
                "request_bbox": _parse_bbox(payload.get("roi_hint")),
                "requested_class_name": (payload.get("metadata") or {}).get("class_name"),
                "metadata": dict(payload.get("metadata") or {}),
            }
            continue
        if event_type != "verification_result":
            continue
        request_id = str(payload.get("request_id"))
        request = pending_requests.get(request_id, {})
        attempts.append(
            LoggedVerificationAttempt(
                request_id=request_id,
                source_timestamp_s=_maybe_float(request.get("source_timestamp_s")),
                target_timestamp_s=_maybe_float(record.get("timestamp")),
                source_camera_id=request.get("source_camera_id"),
                target_camera_id=request.get("target_camera_id"),
                request_bbox=request.get("request_bbox"),
                supporting_bbox=_parse_bbox(payload.get("supporting_bbox")),
                requested_class_name=request.get("requested_class_name"),
                verified=bool(payload.get("verified")),
                verifier_score=float(payload.get("verifier_score", 0.0)),
                failure_reason=payload.get("failure_reason"),
                metadata={
                    **dict(request.get("metadata") or {}),
                    **dict(payload.get("metadata") or {}),
                },
            )
        )
    return attempts


def _find_best_frame_annotation(
    *,
    frames: list[FrameAnnotation],
    camera_id: str,
    timestamp_s: float,
    timestamp_tolerance_s: float,
) -> FrameAnnotation | None:
    candidates: list[tuple[float, FrameAnnotation]] = []
    for frame in frames:
        if frame.camera_id != camera_id:
            continue
        delta = abs(frame.timestamp_s - timestamp_s)
        if delta <= timestamp_tolerance_s + 1e-9:
            candidates.append((delta, frame))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1].annotation_id))
    return candidates[0][1]


def _parse_bbox(raw: Any) -> BBox | None:
    if raw is None:
        return None
    return BBox(
        x1=float(raw["x1"]),
        y1=float(raw["y1"]),
        x2=float(raw["x2"]),
        y2=float(raw["y2"]),
    )


def _maybe_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
