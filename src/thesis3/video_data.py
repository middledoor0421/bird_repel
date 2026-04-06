from __future__ import annotations

from enum import Enum
import json
from pathlib import Path
from typing import Any, Iterable

from thesis3.core import BBox, stable_hash, to_serializable
from thesis3.dataclass_compat import dataclass, field


class AnnotationLabel(str, Enum):
    BIRD_PRESENT = "bird_present"
    BIRD_ABSENT = "bird_absent"
    HARD_NEGATIVE = "hard_negative"
    UNKNOWN = "unknown"


class TaskPurpose(str, Enum):
    EVENT_SCAN = "event_scan"
    FRAME_BOX = "frame_box"


class DatasetSplit(str, Enum):
    TRAIN = "train"
    VAL = "val"
    TEST = "test"


@dataclass(slots=True)
class VideoAsset:
    asset_id: str
    source_path: str
    camera_id: str
    width: int
    height: int
    fps: float
    duration_s: float
    frame_count: int
    codec_name: str | None = None
    file_size_bytes: int | None = None
    creation_time: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ClipTask:
    task_id: str
    asset_id: str
    camera_id: str
    source_path: str
    start_time_s: float
    end_time_s: float
    purpose: TaskPurpose = TaskPurpose.EVENT_SCAN
    status: str = "pending"
    priority: int = 0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EventAnnotation:
    annotation_id: str
    asset_id: str
    camera_id: str
    source_path: str
    start_time_s: float
    end_time_s: float
    label: AnnotationLabel
    task_id: str | None = None
    bird_count_min: int | None = None
    bird_count_max: int | None = None
    quality_tags: list[str] = field(default_factory=list)
    annotator: str | None = None
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FrameObjectAnnotation:
    class_name: str
    bbox: BBox
    object_id: str | None = None
    visibility: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class FrameLabelTask:
    task_id: str
    asset_id: str
    camera_id: str
    source_path: str
    timestamp_s: float
    frame_index: int | None = None
    source_event_annotation_id: str | None = None
    purpose: TaskPurpose = TaskPurpose.FRAME_BOX
    status: str = "pending"
    priority: int = 0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FrameAnnotation:
    annotation_id: str
    asset_id: str
    camera_id: str
    source_path: str
    timestamp_s: float
    frame_index: int | None
    objects: list[FrameObjectAnnotation]
    annotator: str | None = None
    source_event_annotation_id: str | None = None
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExperimentSample:
    sample_id: str
    asset_id: str
    camera_id: str
    source_path: str
    start_time_s: float
    end_time_s: float
    label: AnnotationLabel
    split: DatasetSplit
    purpose: str
    annotation_refs: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def write_jsonl(records: Iterable[Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(to_serializable(record), ensure_ascii=True) + "\n")
    return path


def _read_jsonl_records(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    jsonl_path = Path(path)
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"Each JSONL record must be an object: {jsonl_path}")
        records.append(payload)
    return records


def load_video_assets(path: str | Path) -> list[VideoAsset]:
    return [VideoAsset(**record) for record in _read_jsonl_records(path)]


def load_clip_tasks(path: str | Path) -> list[ClipTask]:
    tasks = []
    for record in _read_jsonl_records(path):
        record["purpose"] = TaskPurpose(record["purpose"])
        tasks.append(ClipTask(**record))
    return tasks


def load_event_annotations(path: str | Path) -> list[EventAnnotation]:
    annotations = []
    for record in _read_jsonl_records(path):
        record["label"] = AnnotationLabel(record["label"])
        annotations.append(EventAnnotation(**record))
    return annotations


def load_frame_label_tasks(path: str | Path) -> list[FrameLabelTask]:
    tasks = []
    for record in _read_jsonl_records(path):
        record["purpose"] = TaskPurpose(record["purpose"])
        tasks.append(FrameLabelTask(**record))
    return tasks


def load_frame_annotations(path: str | Path) -> list[FrameAnnotation]:
    annotations: list[FrameAnnotation] = []
    for record in _read_jsonl_records(path):
        objects = [
            FrameObjectAnnotation(
                class_name=raw_object["class_name"],
                bbox=BBox(*raw_object["bbox"]),
                object_id=raw_object.get("object_id"),
                visibility=raw_object.get("visibility"),
                tags=list(raw_object.get("tags", [])),
            )
            for raw_object in record["objects"]
        ]
        annotations.append(
            FrameAnnotation(
                annotation_id=record["annotation_id"],
                asset_id=record["asset_id"],
                camera_id=record["camera_id"],
                source_path=record["source_path"],
                timestamp_s=float(record["timestamp_s"]),
                frame_index=record.get("frame_index"),
                objects=objects,
                annotator=record.get("annotator"),
                source_event_annotation_id=record.get("source_event_annotation_id"),
                notes=record.get("notes", ""),
                metadata=dict(record.get("metadata", {})),
            )
        )
    return annotations


def load_experiment_samples(path: str | Path) -> list[ExperimentSample]:
    samples = []
    for record in _read_jsonl_records(path):
        record["label"] = AnnotationLabel(record["label"])
        record["split"] = DatasetSplit(record["split"])
        samples.append(ExperimentSample(**record))
    return samples


def infer_camera_id(path: Path, strategy: str = "parent") -> str:
    if strategy == "parent":
        if path.parent.name:
            return path.parent.name
        return path.stem
    if strategy == "stem":
        return path.stem
    if strategy == "prefix":
        return path.stem.split("_", 1)[0]
    raise ValueError(f"Unsupported camera inference strategy: {strategy}")


def build_asset_id(source_path: str, camera_id: str) -> str:
    payload = {"source_path": str(source_path), "camera_id": camera_id}
    return f"{camera_id}-{stable_hash(payload)}"


def generate_clip_tasks(
    assets: list[VideoAsset],
    clip_duration_s: float,
    clip_stride_s: float | None = None,
    include_tail: bool = True,
) -> list[ClipTask]:
    if clip_duration_s <= 0.0:
        raise ValueError("clip_duration_s must be positive.")
    stride_s = clip_stride_s if clip_stride_s is not None else clip_duration_s
    if stride_s <= 0.0:
        raise ValueError("clip_stride_s must be positive.")

    tasks: list[ClipTask] = []
    for asset in assets:
        start_time_s = 0.0
        while start_time_s < asset.duration_s:
            end_time_s = min(asset.duration_s, start_time_s + clip_duration_s)
            if not include_tail and end_time_s - start_time_s < clip_duration_s:
                break
            task_id = f"clip-{asset.asset_id}-{int(round(start_time_s * 1000.0)):08d}"
            tasks.append(
                ClipTask(
                    task_id=task_id,
                    asset_id=asset.asset_id,
                    camera_id=asset.camera_id,
                    source_path=asset.source_path,
                    start_time_s=round(start_time_s, 3),
                    end_time_s=round(end_time_s, 3),
                    metadata={
                        "asset_duration_s": asset.duration_s,
                        "asset_fps": asset.fps,
                    },
                )
            )
            if end_time_s >= asset.duration_s:
                break
            start_time_s += stride_s
    return tasks


def generate_frame_label_tasks(
    events: list[EventAnnotation],
    assets_by_id: dict[str, VideoAsset] | None = None,
    max_frames_per_event: int = 5,
    include_boundary_frames: bool = True,
) -> list[FrameLabelTask]:
    if max_frames_per_event <= 0:
        raise ValueError("max_frames_per_event must be positive.")

    tasks: list[FrameLabelTask] = []
    positive_labels = {AnnotationLabel.BIRD_PRESENT}
    for event in events:
        if event.label not in positive_labels:
            continue

        timestamps = _sample_event_timestamps(
            start_time_s=event.start_time_s,
            end_time_s=event.end_time_s,
            max_samples=max_frames_per_event,
            include_boundaries=include_boundary_frames,
        )
        asset = assets_by_id.get(event.asset_id) if assets_by_id is not None else None
        for index, timestamp_s in enumerate(timestamps):
            frame_index = None
            if asset is not None and asset.fps > 0.0:
                frame_index = int(round(timestamp_s * asset.fps))
            task_id = f"frame-{event.annotation_id}-{index:02d}"
            tasks.append(
                FrameLabelTask(
                    task_id=task_id,
                    asset_id=event.asset_id,
                    camera_id=event.camera_id,
                    source_path=event.source_path,
                    timestamp_s=timestamp_s,
                    frame_index=frame_index,
                    source_event_annotation_id=event.annotation_id,
                    tags=list(event.quality_tags),
                    metadata={
                        "event_start_time_s": event.start_time_s,
                        "event_end_time_s": event.end_time_s,
                    },
                )
            )
    return tasks


def build_experiment_manifest(
    events: list[EventAnnotation],
    negative_ratio: float = 1.0,
    include_hard_negative_always: bool = True,
) -> list[ExperimentSample]:
    if negative_ratio < 0.0:
        raise ValueError("negative_ratio must be non-negative.")

    positives = [event for event in events if event.label == AnnotationLabel.BIRD_PRESENT]
    hard_negatives = [event for event in events if event.label == AnnotationLabel.HARD_NEGATIVE]
    negatives = [event for event in events if event.label == AnnotationLabel.BIRD_ABSENT]

    selected_negatives = list(hard_negatives) if include_hard_negative_always else []
    remaining_budget = max(0, int(round(len(positives) * negative_ratio)) - len(selected_negatives))

    ordered_negatives = sorted(
        negatives,
        key=lambda event: stable_hash({"annotation_id": event.annotation_id, "asset_id": event.asset_id}),
    )
    if remaining_budget > 0:
        selected_negatives.extend(ordered_negatives[:remaining_budget])

    selected_events = positives + selected_negatives
    samples: list[ExperimentSample] = []
    for event in selected_events:
        split = split_for_key(event.asset_id)
        sample_id = f"sample-{event.annotation_id}"
        purpose = "event_detection_eval" if event.label == AnnotationLabel.BIRD_PRESENT else "hard_negative_eval"
        samples.append(
            ExperimentSample(
                sample_id=sample_id,
                asset_id=event.asset_id,
                camera_id=event.camera_id,
                source_path=event.source_path,
                start_time_s=event.start_time_s,
                end_time_s=event.end_time_s,
                label=event.label,
                split=split,
                purpose=purpose,
                annotation_refs=[event.annotation_id],
                tags=list(event.quality_tags),
                metadata={
                    "bird_count_min": event.bird_count_min,
                    "bird_count_max": event.bird_count_max,
                    "task_id": event.task_id,
                },
            )
        )
    return samples


def split_for_key(key: str, train_ratio: float = 0.7, val_ratio: float = 0.15) -> DatasetSplit:
    bucket = int(stable_hash({"key": key}), 16) % 10000 / 10000.0
    if bucket < train_ratio:
        return DatasetSplit.TRAIN
    if bucket < train_ratio + val_ratio:
        return DatasetSplit.VAL
    return DatasetSplit.TEST


def _sample_event_timestamps(
    start_time_s: float,
    end_time_s: float,
    max_samples: int,
    include_boundaries: bool,
) -> list[float]:
    duration_s = max(0.0, end_time_s - start_time_s)
    if duration_s <= 0.0:
        return [round(start_time_s, 3)]

    if max_samples == 1:
        return [round((start_time_s + end_time_s) / 2.0, 3)]

    timestamps: list[float] = []
    if include_boundaries:
        timestamps.append(start_time_s)
        if max_samples > 1:
            timestamps.append(end_time_s)

    remaining = max_samples - len(timestamps)
    if remaining > 0:
        step = duration_s / (remaining + 1)
        for index in range(remaining):
            timestamps.append(start_time_s + step * (index + 1))

    unique_sorted = sorted({round(timestamp, 3) for timestamp in timestamps})
    return unique_sorted[:max_samples]
