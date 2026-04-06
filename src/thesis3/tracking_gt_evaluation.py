from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from thesis3.dataclass_compat import dataclass, field
from thesis3.video_data import FrameAnnotation


DEFAULT_IGNORED_GT_CLASS_NAMES = {"unknown"}


@dataclass(slots=True)
class TrackerObservation:
    observation_id: str
    timestamp: float
    camera_id: str | None
    track_id: str
    object_key: str | None
    state: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TrackingObservationMatch:
    annotation_id: str
    object_id: str
    camera_id: str
    timestamp_s: float
    matched: bool
    matched_track_id: str | None
    matched_object_key: str | None
    observation_id: str | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TrackingObjectSummary:
    object_id: str
    observation_count: int
    matched_observation_count: int
    distinct_track_ids: list[str] = field(default_factory=list)
    id_switch_count: int = 0
    handoff_transition_count: int = 0
    handoff_success_count: int = 0
    handoff_failure_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TrackingGtEvaluationSummary:
    object_count: int
    gt_observation_count: int
    matched_observation_count: int
    missing_observation_count: int
    continuity_recall: float
    object_fragmentation_count: int
    id_switch_count: int
    handoff_transition_count: int
    handoff_success_count: int
    handoff_failure_count: int
    handoff_success_rate: float
    per_object_summaries: list[TrackingObjectSummary] = field(default_factory=list)
    per_observation_matches: list[TrackingObservationMatch] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def evaluate_tracking_ground_truth(
    *,
    event_log_path: str | Path,
    frames: list[FrameAnnotation],
    timestamp_tolerance_s: float = 0.05,
    ignored_gt_class_names: set[str] | None = None,
) -> TrackingGtEvaluationSummary:
    ignored_gt_class_names = ignored_gt_class_names or set(DEFAULT_IGNORED_GT_CLASS_NAMES)
    tracker_observations = load_tracker_observations(event_log_path)
    gt_observations = _build_gt_observations(frames, ignored_gt_class_names)

    per_observation_matches: list[TrackingObservationMatch] = []
    grouped_matches: dict[str, list[TrackingObservationMatch]] = {}
    matched_observation_count = 0

    for gt_obs in gt_observations:
        match = _match_tracker_observation(
            tracker_observations=tracker_observations,
            object_id=gt_obs["object_id"],
            camera_id=gt_obs["camera_id"],
            timestamp_s=gt_obs["timestamp_s"],
            timestamp_tolerance_s=timestamp_tolerance_s,
        )
        obs_match = TrackingObservationMatch(
            annotation_id=gt_obs["annotation_id"],
            object_id=gt_obs["object_id"],
            camera_id=gt_obs["camera_id"],
            timestamp_s=gt_obs["timestamp_s"],
            matched=match is not None,
            matched_track_id=None if match is None else match.track_id,
            matched_object_key=None if match is None else match.object_key,
            observation_id=None if match is None else match.observation_id,
            metadata={
                "class_name": gt_obs["class_name"],
            },
        )
        matched_observation_count += int(obs_match.matched)
        per_observation_matches.append(obs_match)
        grouped_matches.setdefault(obs_match.object_id, []).append(obs_match)

    per_object_summaries: list[TrackingObjectSummary] = []
    object_fragmentation_count = 0
    id_switch_count = 0
    handoff_transition_count = 0
    handoff_success_count = 0
    handoff_failure_count = 0

    for object_id, matches in sorted(grouped_matches.items()):
        ordered = sorted(matches, key=lambda item: (item.timestamp_s, item.annotation_id))
        distinct_track_ids = sorted({item.matched_track_id for item in ordered if item.matched_track_id is not None})
        object_fragmentation_count += max(0, len(distinct_track_ids) - 1)

        object_id_switch_count = 0
        object_handoff_transition_count = 0
        object_handoff_success_count = 0
        object_handoff_failure_count = 0
        for previous, current in zip(ordered, ordered[1:]):
            if previous.matched and current.matched and previous.matched_track_id != current.matched_track_id:
                object_id_switch_count += 1
            if previous.camera_id != current.camera_id:
                object_handoff_transition_count += 1
                if (
                    previous.matched
                    and current.matched
                    and previous.matched_track_id == current.matched_track_id
                ):
                    object_handoff_success_count += 1
                else:
                    object_handoff_failure_count += 1

        id_switch_count += object_id_switch_count
        handoff_transition_count += object_handoff_transition_count
        handoff_success_count += object_handoff_success_count
        handoff_failure_count += object_handoff_failure_count

        per_object_summaries.append(
            TrackingObjectSummary(
                object_id=object_id,
                observation_count=len(ordered),
                matched_observation_count=sum(1 for item in ordered if item.matched),
                distinct_track_ids=distinct_track_ids,
                id_switch_count=object_id_switch_count,
                handoff_transition_count=object_handoff_transition_count,
                handoff_success_count=object_handoff_success_count,
                handoff_failure_count=object_handoff_failure_count,
                metadata={
                    "camera_sequence": [item.camera_id for item in ordered],
                },
            )
        )

    gt_observation_count = len(gt_observations)
    missing_observation_count = gt_observation_count - matched_observation_count
    continuity_recall = matched_observation_count / gt_observation_count if gt_observation_count else 0.0
    handoff_success_rate = (
        handoff_success_count / handoff_transition_count if handoff_transition_count else 0.0
    )

    return TrackingGtEvaluationSummary(
        object_count=len(grouped_matches),
        gt_observation_count=gt_observation_count,
        matched_observation_count=matched_observation_count,
        missing_observation_count=missing_observation_count,
        continuity_recall=continuity_recall,
        object_fragmentation_count=object_fragmentation_count,
        id_switch_count=id_switch_count,
        handoff_transition_count=handoff_transition_count,
        handoff_success_count=handoff_success_count,
        handoff_failure_count=handoff_failure_count,
        handoff_success_rate=handoff_success_rate,
        per_object_summaries=per_object_summaries,
        per_observation_matches=per_observation_matches,
        metadata={
            "event_log_path": str(event_log_path),
            "timestamp_tolerance_s": timestamp_tolerance_s,
            "ignored_gt_class_names": sorted(ignored_gt_class_names),
        },
    )


def format_tracking_gt_evaluation(summary: TrackingGtEvaluationSummary) -> str:
    lines = [
        f"object_count={summary.object_count}",
        f"gt_observation_count={summary.gt_observation_count}",
        f"matched_observation_count={summary.matched_observation_count}",
        f"missing_observation_count={summary.missing_observation_count}",
        f"continuity_recall={summary.continuity_recall:.4f}",
        f"object_fragmentation_count={summary.object_fragmentation_count}",
        f"id_switch_count={summary.id_switch_count}",
        f"handoff_transition_count={summary.handoff_transition_count}",
        f"handoff_success_count={summary.handoff_success_count}",
        f"handoff_failure_count={summary.handoff_failure_count}",
        f"handoff_success_rate={summary.handoff_success_rate:.4f}",
    ]
    return "\n".join(lines)


def load_tracker_observations(event_log_path: str | Path) -> list[TrackerObservation]:
    path = Path(event_log_path)
    observations: list[TrackerObservation] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("event_type") != "tracker_update":
            continue
        payload = record.get("payload", {})
        for track_index, track in enumerate(payload.get("tracks", [])):
            camera_history = list(track.get("camera_history", []))
            camera_id = camera_history[-1] if camera_history else None
            timestamp = track.get("last_seen_time", record.get("timestamp"))
            if timestamp is None:
                continue
            observations.append(
                TrackerObservation(
                    observation_id=f"{path.stem}-tracker-{index:04d}-{track_index:02d}",
                    timestamp=float(timestamp),
                    camera_id=camera_id,
                    track_id=str(track.get("track_id")),
                    object_key=(track.get("metadata") or {}).get("object_key"),
                    state=str(track.get("state")),
                    metadata=dict(track.get("metadata") or {}),
                )
            )
    return observations


def _build_gt_observations(
    frames: list[FrameAnnotation],
    ignored_gt_class_names: set[str],
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for frame in frames:
        for object_index, obj in enumerate(frame.objects):
            if obj.class_name in ignored_gt_class_names:
                continue
            if obj.object_id is None:
                continue
            observations.append(
                {
                    "annotation_id": frame.annotation_id,
                    "object_id": obj.object_id,
                    "class_name": obj.class_name,
                    "camera_id": frame.camera_id,
                    "timestamp_s": frame.timestamp_s,
                    "object_index": object_index,
                }
            )
    observations.sort(key=lambda item: (item["object_id"], item["timestamp_s"], item["annotation_id"]))
    return observations


def _match_tracker_observation(
    *,
    tracker_observations: list[TrackerObservation],
    object_id: str,
    camera_id: str,
    timestamp_s: float,
    timestamp_tolerance_s: float,
) -> TrackerObservation | None:
    candidates: list[tuple[float, TrackerObservation]] = []
    for observation in tracker_observations:
        if observation.object_key != object_id:
            continue
        if observation.camera_id != camera_id:
            continue
        delta = abs(observation.timestamp - timestamp_s)
        if delta <= timestamp_tolerance_s + 1e-9:
            candidates.append((delta, observation))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1].observation_id))
    return candidates[0][1]
