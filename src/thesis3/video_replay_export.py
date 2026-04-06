from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any

from thesis3.core import stable_hash
from thesis3.dataclass_compat import dataclass
from thesis3.video_data import (
    AnnotationLabel,
    DatasetSplit,
    ExperimentSample,
    FrameAnnotation,
    VideoAsset,
    load_experiment_samples,
    load_frame_annotations,
    load_video_assets,
    write_jsonl,
)


@dataclass(slots=True)
class ReplayExportSummary:
    manifest_path: str
    frame_root: str
    sample_count: int
    frame_count: int
    extraction_fps: float


def export_replay_bundle(
    experiment_manifest_path: str | Path,
    video_index_path: str | Path,
    output_dir: str | Path,
    extraction_fps: float,
    image_format: str = "jpg",
    frame_annotations_path: str | Path | None = None,
    include_labels: set[AnnotationLabel] | None = None,
    include_splits: set[DatasetSplit] | None = None,
    max_samples: int | None = None,
) -> ReplayExportSummary:
    if extraction_fps <= 0.0:
        raise ValueError("extraction_fps must be positive.")

    output_root = Path(output_dir)
    frame_root = output_root / "frames"
    output_root.mkdir(parents=True, exist_ok=True)
    frame_root.mkdir(parents=True, exist_ok=True)

    assets = {asset.asset_id: asset for asset in load_video_assets(video_index_path)}
    samples = load_experiment_samples(experiment_manifest_path)
    annotations_by_asset: dict[str, list[FrameAnnotation]] = {}
    if frame_annotations_path is not None:
        for annotation in load_frame_annotations(frame_annotations_path):
            annotations_by_asset.setdefault(annotation.asset_id, []).append(annotation)

    selected_samples = _filter_samples(
        samples=samples,
        include_labels=include_labels,
        include_splits=include_splits,
        max_samples=max_samples,
    )

    manifest_records: list[dict[str, Any]] = []
    total_frames = 0
    for sample in selected_samples:
        asset = assets.get(sample.asset_id)
        if asset is None:
            raise KeyError(f"Missing asset for sample {sample.sample_id}: {sample.asset_id}")

        sample_frame_dir = frame_root / sample.sample_id
        extracted_files = extract_sample_frames(
            sample=sample,
            output_dir=sample_frame_dir,
            extraction_fps=extraction_fps,
            image_format=image_format,
        )
        total_frames += len(extracted_files)
        sample_annotations = annotations_by_asset.get(sample.asset_id, [])
        manifest_records.extend(
            build_replay_manifest_records_for_sample(
                sample=sample,
                asset=asset,
                extracted_files=extracted_files,
                extraction_fps=extraction_fps,
                frame_annotations=sample_annotations,
            )
        )

    manifest_path = output_root / "replay_manifest.jsonl"
    write_jsonl(manifest_records, manifest_path)
    return ReplayExportSummary(
        manifest_path=str(manifest_path),
        frame_root=str(frame_root),
        sample_count=len(selected_samples),
        frame_count=total_frames,
        extraction_fps=extraction_fps,
    )


def extract_sample_frames(
    sample: ExperimentSample,
    output_dir: str | Path,
    extraction_fps: float,
    image_format: str = "jpg",
) -> list[Path]:
    sample_output_dir = Path(output_dir)
    sample_output_dir.mkdir(parents=True, exist_ok=True)
    duration_s = max(0.0, sample.end_time_s - sample.start_time_s)
    if duration_s <= 0.0:
        raise ValueError(f"Sample duration must be positive: {sample.sample_id}")

    output_pattern = sample_output_dir / f"frame_%06d.{image_format}"
    command = [
        "ffmpeg",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{sample.start_time_s:.3f}",
        "-t",
        f"{duration_s:.3f}",
        "-i",
        sample.source_path,
        "-vf",
        f"fps={extraction_fps}",
    ]
    if image_format.lower() in {"jpg", "jpeg"}:
        command.extend(["-q:v", "2"])
    command.append(str(output_pattern))
    subprocess.run(command, check=True, capture_output=True, text=True)
    return sorted(sample_output_dir.glob(f"frame_*.{image_format}"))


def build_replay_manifest_records_for_sample(
    sample: ExperimentSample,
    asset: VideoAsset,
    extracted_files: list[Path],
    extraction_fps: float,
    frame_annotations: list[FrameAnnotation] | None = None,
) -> list[dict[str, Any]]:
    frame_annotations = frame_annotations or []
    records: list[dict[str, Any]] = []
    timeline_offset_s = _resolve_timeline_offset_s(sample=sample, asset=asset)
    frame_interval_s = 1.0 / extraction_fps
    for index, frame_path in enumerate(extracted_files):
        local_offset_s = index * frame_interval_s
        source_timestamp_s = round(sample.start_time_s + local_offset_s, 6)
        aligned_timestamp_s = round(timeline_offset_s + source_timestamp_s, 6)
        closest_annotation = _match_frame_annotation(
            annotations=frame_annotations,
            source_timestamp_s=source_timestamp_s,
            tolerance_s=frame_interval_s / 2.0,
        )
        metadata: dict[str, Any] = {
            "asset_id": sample.asset_id,
            "sample_id": sample.sample_id,
            "sample_label": sample.label.value,
            "sample_split": sample.split.value,
            "sample_purpose": sample.purpose,
            "source_video_path": sample.source_path,
            "source_start_time_s": sample.start_time_s,
            "source_end_time_s": sample.end_time_s,
            "source_timestamp_s": source_timestamp_s,
            "sample_local_timestamp_s": round(local_offset_s, 6),
            "camera_fps": asset.fps,
            "extraction_fps": extraction_fps,
            "tags": list(sample.tags),
        }
        if closest_annotation is not None:
            metadata["gt_objects"] = [
                {
                    "class_name": obj.class_name,
                    "bbox": [obj.bbox.x1, obj.bbox.y1, obj.bbox.x2, obj.bbox.y2],
                    "object_id": obj.object_id,
                    "visibility": obj.visibility,
                    "tags": list(obj.tags),
                }
                for obj in closest_annotation.objects
            ]
            metadata["gt_annotation_id"] = closest_annotation.annotation_id

        frame_id = f"{sample.sample_id}-{index:06d}"
        records.append(
            {
                "frame_id": frame_id,
                "camera_id": sample.camera_id,
                "timestamp": aligned_timestamp_s,
                "image_ref": str(frame_path),
                "metadata": metadata,
            }
        )
    return records


def _resolve_timeline_offset_s(sample: ExperimentSample, asset: VideoAsset) -> float:
    sample_offset = sample.metadata.get("timeline_offset_s")
    if sample_offset is not None:
        return float(sample_offset)
    asset_offset = asset.metadata.get("timeline_offset_s")
    if asset_offset is not None:
        return float(asset_offset)
    return 0.0


def _match_frame_annotation(
    annotations: list[FrameAnnotation],
    source_timestamp_s: float,
    tolerance_s: float,
) -> FrameAnnotation | None:
    closest: FrameAnnotation | None = None
    closest_error: float | None = None
    for annotation in annotations:
        error = abs(annotation.timestamp_s - source_timestamp_s)
        if error > tolerance_s:
            continue
        if closest is None or closest_error is None or error < closest_error:
            closest = annotation
            closest_error = error
    return closest


def _filter_samples(
    samples: list[ExperimentSample],
    include_labels: set[AnnotationLabel] | None,
    include_splits: set[DatasetSplit] | None,
    max_samples: int | None,
) -> list[ExperimentSample]:
    selected = []
    for sample in samples:
        if include_labels is not None and sample.label not in include_labels:
            continue
        if include_splits is not None and sample.split not in include_splits:
            continue
        selected.append(sample)
    if max_samples is not None:
        return selected[:max_samples]
    return selected


def parse_annotation_labels(raw_values: list[str] | None) -> set[AnnotationLabel] | None:
    if not raw_values:
        return None
    return {AnnotationLabel(value) for value in raw_values}


def parse_dataset_splits(raw_values: list[str] | None) -> set[DatasetSplit] | None:
    if not raw_values:
        return None
    return {DatasetSplit(value) for value in raw_values}


def build_sample_debug_id(sample: ExperimentSample) -> str:
    return stable_hash(
        {
            "sample_id": sample.sample_id,
            "asset_id": sample.asset_id,
            "start_time_s": sample.start_time_s,
            "end_time_s": sample.end_time_s,
        }
    )
