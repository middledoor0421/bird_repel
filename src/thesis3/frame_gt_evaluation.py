from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from thesis3.core import BBox
from thesis3.dataclass_compat import dataclass, field
from thesis3.video_data import FrameAnnotation


DEFAULT_IGNORED_GT_CLASS_NAMES = {"unknown"}


@dataclass(slots=True)
class LoggedDetection:
    candidate_id: str
    class_name: str
    score: float
    bbox: BBox | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DetectorFrameObservation:
    observation_id: str
    timestamp: float
    camera_id: str | None
    frame_id: str | None
    image_ref: str | None
    detections: list[LoggedDetection] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FrameGtMatch:
    annotation_id: str
    camera_id: str
    timestamp_s: float
    observation_id: str | None
    outcome: str
    gt_object_count: int
    predicted_object_count: int
    tp_count: int
    fn_count: int
    fp_count: int
    matched_pairs: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FrameGtEvaluationSummary:
    annotated_frame_count: int
    positive_frame_count: int
    negative_frame_count: int
    matched_frame_count: int
    missing_observation_count: int
    gt_object_count: int
    predicted_object_count_on_annotated_frames: int
    true_positive_count: int
    false_negative_count: int
    false_positive_count: int
    precision: float
    recall: float
    per_frame_matches: list[FrameGtMatch] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def evaluate_frame_ground_truth(
    *,
    event_log_path: str | Path,
    frames: list[FrameAnnotation],
    iou_threshold: float = 0.5,
    timestamp_tolerance_s: float = 0.05,
    class_agnostic: bool = False,
    ignored_gt_class_names: set[str] | None = None,
) -> FrameGtEvaluationSummary:
    ignored_gt_class_names = ignored_gt_class_names or set(DEFAULT_IGNORED_GT_CLASS_NAMES)
    observations = load_detector_observations(event_log_path)
    unmatched_observations = {observation.observation_id: observation for observation in observations}
    per_frame_matches: list[FrameGtMatch] = []

    positive_frame_count = 0
    negative_frame_count = 0
    matched_frame_count = 0
    missing_observation_count = 0
    gt_object_count = 0
    predicted_object_count_on_annotated_frames = 0
    true_positive_count = 0
    false_negative_count = 0
    false_positive_count = 0

    for frame in frames:
        gt_objects = [
            obj for obj in frame.objects
            if obj.class_name not in ignored_gt_class_names
        ]
        gt_object_count += len(gt_objects)
        if gt_objects:
            positive_frame_count += 1
        else:
            negative_frame_count += 1

        observation = _find_best_observation(
            observations=observations,
            frame=frame,
            timestamp_tolerance_s=timestamp_tolerance_s,
        )
        if observation is None:
            missing_observation_count += 1
            false_negative_count += len(gt_objects)
            per_frame_matches.append(
                FrameGtMatch(
                    annotation_id=frame.annotation_id,
                    camera_id=frame.camera_id,
                    timestamp_s=frame.timestamp_s,
                    observation_id=None,
                    outcome="missing_observation",
                    gt_object_count=len(gt_objects),
                    predicted_object_count=0,
                    tp_count=0,
                    fn_count=len(gt_objects),
                    fp_count=0,
                    metadata={"notes": frame.notes},
                )
            )
            continue

        matched_frame_count += 1
        unmatched_observations.pop(observation.observation_id, None)
        predicted_object_count_on_annotated_frames += len(observation.detections)
        gt_matches, fp_count, fn_count = _match_detections_to_gt(
            gt_objects=gt_objects,
            detections=observation.detections,
            iou_threshold=iou_threshold,
            class_agnostic=class_agnostic,
        )
        tp_count = len(gt_matches)
        true_positive_count += tp_count
        false_negative_count += fn_count
        false_positive_count += fp_count

        if len(gt_objects) == 0 and fp_count == 0:
            outcome = "clean_negative"
        elif len(gt_objects) == 0 and fp_count > 0:
            outcome = "false_positive"
        elif tp_count == len(gt_objects) and fp_count == 0:
            outcome = "matched"
        elif tp_count == 0 and len(gt_objects) > 0:
            outcome = "miss"
        else:
            outcome = "partial"

        per_frame_matches.append(
            FrameGtMatch(
                annotation_id=frame.annotation_id,
                camera_id=frame.camera_id,
                timestamp_s=frame.timestamp_s,
                observation_id=observation.observation_id,
                outcome=outcome,
                gt_object_count=len(gt_objects),
                predicted_object_count=len(observation.detections),
                tp_count=tp_count,
                fn_count=fn_count,
                fp_count=fp_count,
                matched_pairs=gt_matches,
                metadata={
                    "frame_notes": frame.notes,
                    "frame_id": observation.frame_id,
                    "image_ref": observation.image_ref,
                },
            )
        )

    precision = (
        true_positive_count / (true_positive_count + false_positive_count)
        if (true_positive_count + false_positive_count)
        else 0.0
    )
    recall = (
        true_positive_count / (true_positive_count + false_negative_count)
        if (true_positive_count + false_negative_count)
        else 0.0
    )

    return FrameGtEvaluationSummary(
        annotated_frame_count=len(frames),
        positive_frame_count=positive_frame_count,
        negative_frame_count=negative_frame_count,
        matched_frame_count=matched_frame_count,
        missing_observation_count=missing_observation_count,
        gt_object_count=gt_object_count,
        predicted_object_count_on_annotated_frames=predicted_object_count_on_annotated_frames,
        true_positive_count=true_positive_count,
        false_negative_count=false_negative_count,
        false_positive_count=false_positive_count,
        precision=precision,
        recall=recall,
        per_frame_matches=per_frame_matches,
        metadata={
            "event_log_path": str(event_log_path),
            "iou_threshold": iou_threshold,
            "timestamp_tolerance_s": timestamp_tolerance_s,
            "class_agnostic": class_agnostic,
            "ignored_gt_class_names": sorted(ignored_gt_class_names),
            "unmatched_detector_observation_count": len(unmatched_observations),
        },
    )


def format_frame_gt_evaluation(summary: FrameGtEvaluationSummary) -> str:
    lines = [
        f"annotated_frame_count={summary.annotated_frame_count}",
        f"positive_frame_count={summary.positive_frame_count}",
        f"negative_frame_count={summary.negative_frame_count}",
        f"matched_frame_count={summary.matched_frame_count}",
        f"missing_observation_count={summary.missing_observation_count}",
        f"gt_object_count={summary.gt_object_count}",
        f"predicted_object_count_on_annotated_frames={summary.predicted_object_count_on_annotated_frames}",
        f"true_positive_count={summary.true_positive_count}",
        f"false_negative_count={summary.false_negative_count}",
        f"false_positive_count={summary.false_positive_count}",
        f"precision={summary.precision:.4f}",
        f"recall={summary.recall:.4f}",
    ]
    return "\n".join(lines)


def load_detector_observations(event_log_path: str | Path) -> list[DetectorFrameObservation]:
    observations: list[DetectorFrameObservation] = []
    path = Path(event_log_path)
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("event_type") != "detector_result":
            continue
        payload = record.get("payload", {})
        wrapped = payload.get("result")
        frame_id = payload.get("frame_id")
        camera_id = payload.get("camera_id")
        image_ref = payload.get("image_ref")
        source_timestamp = payload.get("timestamp", record.get("timestamp"))
        detector_payload = wrapped if isinstance(wrapped, dict) else payload
        candidates = detector_payload.get("candidates", [])
        diagnostics = dict(detector_payload.get("diagnostics", {}))
        if camera_id is None and candidates:
            camera_id = candidates[0].get("camera_id")
        if frame_id is None and candidates:
            frame_id = candidates[0].get("frame_id")
        if source_timestamp is None:
            continue
        detections = []
        for candidate in candidates:
            bbox_payload = candidate.get("bbox")
            bbox = None
            if bbox_payload is not None:
                bbox = BBox(
                    x1=float(bbox_payload["x1"]),
                    y1=float(bbox_payload["y1"]),
                    x2=float(bbox_payload["x2"]),
                    y2=float(bbox_payload["y2"]),
                )
            detections.append(
                LoggedDetection(
                    candidate_id=str(candidate.get("candidate_id")),
                    class_name=str(candidate.get("class_name")),
                    score=float(candidate.get("detector_confidence", 0.0)),
                    bbox=bbox,
                    metadata=dict(candidate.get("metadata", {})),
                )
            )
        observations.append(
            DetectorFrameObservation(
                observation_id=f"{path.stem}-detector-{index:04d}",
                timestamp=float(source_timestamp),
                camera_id=str(camera_id) if camera_id is not None else None,
                frame_id=str(frame_id) if frame_id is not None else None,
                image_ref=str(image_ref) if image_ref is not None else None,
                detections=detections,
                diagnostics=diagnostics,
            )
        )
    return observations


def _find_best_observation(
    *,
    observations: list[DetectorFrameObservation],
    frame: FrameAnnotation,
    timestamp_tolerance_s: float,
) -> DetectorFrameObservation | None:
    candidates = []
    for observation in observations:
        if observation.camera_id is not None and observation.camera_id != frame.camera_id:
            continue
        delta = abs(observation.timestamp - frame.timestamp_s)
        if delta <= timestamp_tolerance_s + 1e-9:
            candidates.append((delta, observation))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1].observation_id))
    return candidates[0][1]


def _match_detections_to_gt(
    *,
    gt_objects: list[Any],
    detections: list[LoggedDetection],
    iou_threshold: float,
    class_agnostic: bool,
) -> tuple[list[dict[str, Any]], int, int]:
    potential_pairs: list[tuple[float, int, int]] = []
    for gt_index, gt_object in enumerate(gt_objects):
        for det_index, detection in enumerate(detections):
            if detection.bbox is None:
                continue
            if not class_agnostic and detection.class_name != gt_object.class_name:
                continue
            iou = compute_iou(gt_object.bbox, detection.bbox)
            if iou >= iou_threshold:
                potential_pairs.append((iou, gt_index, det_index))
    potential_pairs.sort(key=lambda item: (-item[0], item[1], item[2]))

    matched_gt: set[int] = set()
    matched_det: set[int] = set()
    matches: list[dict[str, Any]] = []
    for iou, gt_index, det_index in potential_pairs:
        if gt_index in matched_gt or det_index in matched_det:
            continue
        matched_gt.add(gt_index)
        matched_det.add(det_index)
        matches.append(
            {
                "gt_index": gt_index,
                "det_index": det_index,
                "iou": iou,
                "gt_class_name": gt_objects[gt_index].class_name,
                "det_class_name": detections[det_index].class_name,
                "det_score": detections[det_index].score,
            }
        )

    fp_count = len(detections) - len(matched_det)
    fn_count = len(gt_objects) - len(matched_gt)
    return matches, fp_count, fn_count


def compute_iou(lhs: BBox, rhs: BBox) -> float:
    intersection_x1 = max(lhs.x1, rhs.x1)
    intersection_y1 = max(lhs.y1, rhs.y1)
    intersection_x2 = min(lhs.x2, rhs.x2)
    intersection_y2 = min(lhs.y2, rhs.y2)
    intersection = BBox(intersection_x1, intersection_y1, intersection_x2, intersection_y2).area
    union = lhs.area + rhs.area - intersection
    if union <= 0.0:
        return 0.0
    return intersection / union
