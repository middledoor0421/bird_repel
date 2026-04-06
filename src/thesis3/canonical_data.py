from __future__ import annotations

from enum import Enum
import json
from pathlib import Path
from typing import Any

from thesis3.camera_inventory import (
    CalibrationRegistryRecord,
    CameraInventoryRecord,
    calibration_registry_by_ref,
    camera_inventory_by_id,
)
from thesis3.core import stable_hash
from thesis3.dataclass_compat import dataclass, field
from thesis3.replay import ReplayManifestReader
from thesis3.video_data import VideoAsset, write_jsonl

CANONICAL_SCHEMA_VERSION = "v1"


class LabelStatus(str, Enum):
    UNLABELED = "unlabeled"
    WEAK = "weak"
    LABELED = "labeled"
    VERIFIED = "verified"
    IGNORED = "ignored"


class SplitTag(str, Enum):
    UNSPECIFIED = "unspecified"
    TRAIN = "train"
    VAL = "val"
    TEST = "test"
    HOLDOUT = "holdout"


@dataclass(slots=True)
class CanonicalSequence:
    sequence_id: str
    asset_id: str
    camera_id: str
    source_ref: str
    source_type: str
    start_timestamp_s: float
    end_timestamp_s: float
    fps: float
    width: int
    height: int
    calibration_ref: str | None = None
    environment_tag: str = "unknown"
    label_status: LabelStatus = LabelStatus.UNLABELED
    split_tag: SplitTag = SplitTag.UNSPECIFIED
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CanonicalFrameSample:
    sample_id: str
    sequence_id: str
    camera_id: str
    timestamp_s: float
    image_ref: str
    calibration_ref: str | None = None
    environment_tag: str = "unknown"
    label_status: LabelStatus = LabelStatus.UNLABELED
    split_tag: SplitTag = SplitTag.UNSPECIFIED
    source_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def load_calibration_map(path: str | Path | None) -> dict[str, str]:
    if path is None:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Calibration map must be a JSON object of camera_id -> calibration_ref.")
    return {str(key): str(value) for key, value in payload.items()}


def build_canonical_sequences_from_assets(
    assets: list[VideoAsset],
    *,
    environment_tag: str = "unknown",
    calibration_map: dict[str, str] | None = None,
    camera_inventory: list[CameraInventoryRecord] | None = None,
    calibration_registry: list[CalibrationRegistryRecord] | None = None,
    default_split_tag: SplitTag = SplitTag.UNSPECIFIED,
    default_label_status: LabelStatus = LabelStatus.UNLABELED,
) -> list[CanonicalSequence]:
    calibration_map = calibration_map or {}
    inventory_by_id = camera_inventory_by_id(camera_inventory or [])
    calibration_by_ref = calibration_registry_by_ref(calibration_registry or [])
    sequences: list[CanonicalSequence] = []
    for asset in assets:
        sequence_id = _build_sequence_id(asset.asset_id, asset.camera_id, asset.source_path)
        camera_record = inventory_by_id.get(asset.camera_id)
        calibration_ref = _resolve_calibration_ref(asset.camera_id, calibration_map, camera_record)
        calibration_record = calibration_by_ref.get(calibration_ref) if calibration_ref else None
        resolved_environment_tag = camera_record.environment_tag if camera_record and camera_record.environment_tag else environment_tag
        sequences.append(
            CanonicalSequence(
                sequence_id=sequence_id,
                asset_id=asset.asset_id,
                camera_id=asset.camera_id,
                source_ref=asset.source_path,
                source_type="mp4",
                start_timestamp_s=0.0,
                end_timestamp_s=float(asset.duration_s),
                fps=float(asset.fps),
                width=int(asset.width),
                height=int(asset.height),
                calibration_ref=calibration_ref,
                environment_tag=resolved_environment_tag,
                label_status=default_label_status,
                split_tag=default_split_tag,
                metadata={
                    "schema_version": CANONICAL_SCHEMA_VERSION,
                    "camera_role": None if camera_record is None else camera_record.role,
                    "site_id": None if camera_record is None else camera_record.site_id,
                    "installation_id": None if camera_record is None else camera_record.installation_id,
                    "timezone": None if camera_record is None else camera_record.timezone,
                    "source_type": "mp4" if camera_record is None else camera_record.source_type,
                    "safe_zone_ref": None if camera_record is None else camera_record.safe_zone_ref,
                    "stream_uri_ref": None if camera_record is None else camera_record.stream_uri_ref,
                    "mount_height_m": None if camera_record is None else camera_record.mount_height_m,
                    "view_direction_deg": None if camera_record is None else camera_record.view_direction_deg,
                    "is_ptz": None if camera_record is None else camera_record.is_ptz,
                    "camera_inventory_metadata": {} if camera_record is None else dict(camera_record.metadata),
                    "calibration_metadata": {} if calibration_record is None else dict(calibration_record.metadata),
                    "frame_count": int(asset.frame_count),
                    "codec_name": asset.codec_name,
                    "file_size_bytes": asset.file_size_bytes,
                    "creation_time": asset.creation_time,
                    "source_asset_metadata": dict(asset.metadata),
                },
            )
        )
    return sequences


def build_canonical_frame_samples_from_replay_manifest(
    manifest_path: str | Path,
    *,
    environment_tag: str = "unknown",
    calibration_map: dict[str, str] | None = None,
    camera_inventory: list[CameraInventoryRecord] | None = None,
    calibration_registry: list[CalibrationRegistryRecord] | None = None,
    default_split_tag: SplitTag = SplitTag.UNSPECIFIED,
    default_label_status: LabelStatus = LabelStatus.UNLABELED,
) -> list[CanonicalFrameSample]:
    calibration_map = calibration_map or {}
    inventory_by_id = camera_inventory_by_id(camera_inventory or [])
    calibration_by_ref = calibration_registry_by_ref(calibration_registry or [])
    reader = ReplayManifestReader(manifest_path)
    packets = reader.read_packets()
    samples: list[CanonicalFrameSample] = []
    for packet in packets:
        sequence_id = _resolve_sequence_id(packet)
        split_tag = _coerce_split_tag(packet.metadata.get("sample_split"), default_split_tag)
        label_status = _resolve_label_status(packet.metadata, default_label_status)
        sample_id = str(packet.metadata.get("sample_id") or _build_sample_id(sequence_id, packet.frame_id, packet.timestamp))
        camera_record = inventory_by_id.get(packet.camera_id)
        calibration_ref = _resolve_calibration_ref(packet.camera_id, calibration_map, camera_record)
        calibration_record = calibration_by_ref.get(calibration_ref) if calibration_ref else None
        resolved_environment_tag = camera_record.environment_tag if camera_record and camera_record.environment_tag else environment_tag
        samples.append(
            CanonicalFrameSample(
                sample_id=sample_id,
                sequence_id=sequence_id,
                camera_id=packet.camera_id,
                timestamp_s=float(packet.timestamp),
                image_ref=packet.image_ref,
                calibration_ref=calibration_ref,
                environment_tag=resolved_environment_tag,
                label_status=label_status,
                split_tag=split_tag,
                source_ref=str(packet.metadata.get("source_video_path") or packet.image_ref),
                metadata={
                    "schema_version": CANONICAL_SCHEMA_VERSION,
                    "camera_role": None if camera_record is None else camera_record.role,
                    "site_id": None if camera_record is None else camera_record.site_id,
                    "installation_id": None if camera_record is None else camera_record.installation_id,
                    "timezone": None if camera_record is None else camera_record.timezone,
                    "safe_zone_ref": None if camera_record is None else camera_record.safe_zone_ref,
                    "stream_uri_ref": None if camera_record is None else camera_record.stream_uri_ref,
                    "mount_height_m": None if camera_record is None else camera_record.mount_height_m,
                    "view_direction_deg": None if camera_record is None else camera_record.view_direction_deg,
                    "is_ptz": None if camera_record is None else camera_record.is_ptz,
                    "camera_inventory_metadata": {} if camera_record is None else dict(camera_record.metadata),
                    "calibration_metadata": {} if calibration_record is None else dict(calibration_record.metadata),
                    "frame_id": packet.frame_id,
                    "sync_status": packet.sync_status.value,
                    "source_timestamp_s": packet.metadata.get("source_timestamp_s"),
                    "source_start_time_s": packet.metadata.get("source_start_time_s"),
                    "sample_label": packet.metadata.get("sample_label"),
                    "quality_score": packet.metadata.get("quality_score"),
                    "has_gt_objects": bool(packet.metadata.get("gt_objects")),
                    "source_metadata": dict(packet.metadata),
                },
            )
        )
    return samples


def export_canonical_dataset(
    *,
    video_assets: list[VideoAsset] | None = None,
    replay_manifest_path: str | Path | None = None,
    output_dir: str | Path,
    environment_tag: str = "unknown",
    calibration_map: dict[str, str] | None = None,
    camera_inventory: list[CameraInventoryRecord] | None = None,
    calibration_registry: list[CalibrationRegistryRecord] | None = None,
    default_split_tag: SplitTag = SplitTag.UNSPECIFIED,
    default_label_status: LabelStatus = LabelStatus.UNLABELED,
) -> dict[str, str]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    written_paths: dict[str, str] = {}

    if video_assets is not None:
        sequence_records = build_canonical_sequences_from_assets(
            video_assets,
            environment_tag=environment_tag,
            calibration_map=calibration_map,
            camera_inventory=camera_inventory,
            calibration_registry=calibration_registry,
            default_split_tag=default_split_tag,
            default_label_status=default_label_status,
        )
        sequence_path = output_root / "canonical_sequences.jsonl"
        write_jsonl(sequence_records, sequence_path)
        written_paths["canonical_sequences"] = str(sequence_path)

    if replay_manifest_path is not None:
        frame_records = build_canonical_frame_samples_from_replay_manifest(
            replay_manifest_path,
            environment_tag=environment_tag,
            calibration_map=calibration_map,
            camera_inventory=camera_inventory,
            calibration_registry=calibration_registry,
            default_split_tag=default_split_tag,
            default_label_status=default_label_status,
        )
        frame_path = output_root / "canonical_frame_samples.jsonl"
        write_jsonl(frame_records, frame_path)
        written_paths["canonical_frame_samples"] = str(frame_path)

    if not written_paths:
        raise ValueError("At least one of video_assets or replay_manifest_path must be provided.")
    return written_paths


def _build_sequence_id(asset_id: str, camera_id: str, source_ref: str) -> str:
    return f"{camera_id}-seq-{stable_hash({'asset_id': asset_id, 'source_ref': source_ref})}"


def _build_sample_id(sequence_id: str, frame_id: str, timestamp_s: float) -> str:
    return f"{sequence_id}-sample-{stable_hash({'frame_id': frame_id, 'timestamp_s': timestamp_s})}"


def _resolve_sequence_id(packet: Any) -> str:
    metadata = packet.metadata
    if metadata.get("sequence_id"):
        return str(metadata["sequence_id"])
    if metadata.get("asset_id"):
        return f"{packet.camera_id}-seq-{stable_hash({'asset_id': metadata['asset_id'], 'camera_id': packet.camera_id})}"
    if metadata.get("source_video_path"):
        return f"{packet.camera_id}-seq-{stable_hash({'source_video_path': metadata['source_video_path'], 'camera_id': packet.camera_id})}"
    return f"{packet.camera_id}-seq-{stable_hash({'camera_id': packet.camera_id, 'frame_id': packet.frame_id})}"


def _coerce_split_tag(raw_value: Any, default_value: SplitTag) -> SplitTag:
    if raw_value is None:
        return default_value
    try:
        return SplitTag(str(raw_value))
    except ValueError:
        return default_value


def _resolve_label_status(metadata: dict[str, Any], default_value: LabelStatus) -> LabelStatus:
    if metadata.get("gt_objects"):
        return LabelStatus.LABELED
    sample_label = metadata.get("sample_label")
    if sample_label not in {None, "", "unknown"}:
        return LabelStatus.WEAK
    return default_value


def _resolve_calibration_ref(
    camera_id: str,
    calibration_map: dict[str, str],
    camera_record: CameraInventoryRecord | None,
) -> str | None:
    if camera_record is not None and camera_record.calibration_ref:
        return camera_record.calibration_ref
    return calibration_map.get(camera_id)
