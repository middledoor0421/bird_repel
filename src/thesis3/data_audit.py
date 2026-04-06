from __future__ import annotations

from collections import Counter, defaultdict
from io import BytesIO
import json
from pathlib import Path
import subprocess
from typing import Any

import numpy as np
from PIL import Image

from thesis3.camera_inventory import (
    CalibrationRegistryRecord,
    CameraInventoryRecord,
    calibration_registry_by_ref,
    camera_inventory_by_id,
    source_type_requires_stream_ref,
)
from thesis3.dataclass_compat import dataclass, field
from thesis3.image_io import load_rgb_image, normalized_grayscale_mean, normalized_grayscale_std
from thesis3.replay import ReplayManifestReader
from thesis3.video_data import VideoAsset


@dataclass(slots=True)
class AuditIssue:
    severity: str
    code: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class QualitySample:
    source_ref: str
    camera_id: str
    timestamp_s: float | None
    brightness_mean: float
    contrast_score: float
    sharpness_score: float
    dark_clipped_ratio: float
    bright_clipped_ratio: float
    width: int
    height: int


@dataclass(slots=True)
class DataAuditReport:
    source_type: str
    asset_count: int
    camera_count: int
    summary: dict[str, Any]
    per_camera: dict[str, Any]
    issues: list[AuditIssue] = field(default_factory=list)
    quality_samples: list[QualitySample] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def audit_video_assets(
    assets: list[VideoAsset],
    *,
    sample_frames_per_asset: int = 0,
    camera_inventory: list[CameraInventoryRecord] | None = None,
    calibration_registry: list[CalibrationRegistryRecord] | None = None,
) -> DataAuditReport:
    per_camera_assets: dict[str, list[VideoAsset]] = defaultdict(list)
    for asset in assets:
        per_camera_assets[asset.camera_id].append(asset)
    inventory_by_id = camera_inventory_by_id(camera_inventory or [])
    calibration_by_ref = calibration_registry_by_ref(calibration_registry or [])

    issues: list[AuditIssue] = []
    fps_counter = Counter()
    resolution_counter = Counter()
    codec_counter = Counter()
    total_duration_s = 0.0
    missing_creation_time_count = 0
    zero_geometry_count = 0
    zero_fps_count = 0
    zero_frame_count = 0

    for asset in assets:
        fps_counter[_format_number(asset.fps)] += 1
        resolution_counter[f"{asset.width}x{asset.height}"] += 1
        codec_counter[str(asset.codec_name or "unknown")] += 1
        total_duration_s += float(asset.duration_s)
        if not asset.creation_time:
            missing_creation_time_count += 1
        if asset.width <= 0 or asset.height <= 0:
            zero_geometry_count += 1
            issues.append(
                AuditIssue(
                    severity="error",
                    code="invalid_geometry",
                    message="Video asset has zero or missing width/height.",
                    context={"asset_id": asset.asset_id, "source_path": asset.source_path},
                )
            )
        if asset.fps <= 0.0:
            zero_fps_count += 1
            issues.append(
                AuditIssue(
                    severity="warning",
                    code="invalid_fps",
                    message="Video asset has zero or missing fps.",
                    context={"asset_id": asset.asset_id, "source_path": asset.source_path},
                )
            )
        if asset.frame_count <= 0:
            zero_frame_count += 1
        camera_record = inventory_by_id.get(asset.camera_id)
        if camera_record is None:
            issues.append(
                AuditIssue(
                    severity="warning",
                    code="missing_camera_inventory",
                    message="Camera is not present in camera inventory.",
                    context={"camera_id": asset.camera_id, "asset_id": asset.asset_id},
                )
            )
        else:
            if not camera_record.installation_id:
                issues.append(
                    AuditIssue(
                        severity="warning",
                        code="missing_installation_id",
                        message="Camera inventory entry has no installation_id.",
                        context={"camera_id": asset.camera_id},
                    )
                )
            if camera_record.calibration_ref is None:
                issues.append(
                    AuditIssue(
                        severity="warning",
                        code="missing_calibration_ref",
                        message="Camera inventory entry has no calibration_ref.",
                        context={"camera_id": asset.camera_id},
                    )
                )
            elif calibration_by_ref and camera_record.calibration_ref not in calibration_by_ref:
                issues.append(
                    AuditIssue(
                        severity="warning",
                        code="missing_calibration_registry_entry",
                        message="calibration_ref is missing from calibration registry.",
                        context={"camera_id": asset.camera_id, "calibration_ref": camera_record.calibration_ref},
                    )
                )
            if camera_record.expected_fps is not None and asset.fps > 0.0:
                if abs(float(asset.fps) - float(camera_record.expected_fps)) > 0.5:
                    issues.append(
                        AuditIssue(
                            severity="warning",
                            code="expected_fps_mismatch",
                            message="Observed asset fps deviates from camera inventory expected_fps.",
                            context={
                                "camera_id": asset.camera_id,
                                "observed_fps": asset.fps,
                                "expected_fps": camera_record.expected_fps,
                            },
                        )
                    )
            if camera_record.role in {"primary", "verification"} and not camera_record.safe_zone_ref:
                issues.append(
                    AuditIssue(
                        severity="warning",
                        code="missing_safe_zone_ref",
                        message="Actionable camera inventory entry has no safe_zone_ref.",
                        context={"camera_id": asset.camera_id, "role": camera_record.role},
                    )
                )
            if source_type_requires_stream_ref(camera_record.source_type) and not camera_record.stream_uri_ref:
                issues.append(
                    AuditIssue(
                        severity="warning",
                        code="missing_stream_uri_ref",
                        message="Live camera inventory entry has no stream_uri_ref.",
                        context={"camera_id": asset.camera_id, "source_type": camera_record.source_type},
                    )
                )
            if camera_record.mount_height_m is not None and float(camera_record.mount_height_m) <= 0.0:
                issues.append(
                    AuditIssue(
                        severity="warning",
                        code="invalid_mount_height",
                        message="mount_height_m must be positive when provided.",
                        context={"camera_id": asset.camera_id, "mount_height_m": camera_record.mount_height_m},
                    )
                )
            if camera_record.view_direction_deg is not None:
                view_direction = float(camera_record.view_direction_deg)
                if not 0.0 <= view_direction < 360.0:
                    issues.append(
                        AuditIssue(
                            severity="warning",
                            code="invalid_view_direction",
                            message="view_direction_deg must be in [0, 360).",
                            context={"camera_id": asset.camera_id, "view_direction_deg": camera_record.view_direction_deg},
                        )
                    )
            if camera_record.expected_width is not None and camera_record.expected_height is not None:
                if (asset.width, asset.height) != (camera_record.expected_width, camera_record.expected_height):
                    issues.append(
                        AuditIssue(
                            severity="warning",
                            code="expected_resolution_mismatch",
                            message="Observed asset resolution deviates from camera inventory expected resolution.",
                            context={
                                "camera_id": asset.camera_id,
                                "observed_resolution": f"{asset.width}x{asset.height}",
                                "expected_resolution": f"{camera_record.expected_width}x{camera_record.expected_height}",
                            },
                        )
                    )

    for camera_id, camera_assets in per_camera_assets.items():
        fps_values = {round(asset.fps, 6) for asset in camera_assets}
        resolution_values = {(asset.width, asset.height) for asset in camera_assets}
        if len(fps_values) > 1:
            issues.append(
                AuditIssue(
                    severity="warning",
                    code="camera_fps_mismatch",
                    message="Camera has multiple fps values across assets.",
                    context={"camera_id": camera_id, "fps_values": sorted(fps_values)},
                )
            )
        if len(resolution_values) > 1:
            issues.append(
                AuditIssue(
                    severity="warning",
                    code="camera_resolution_mismatch",
                    message="Camera has multiple resolutions across assets.",
                    context={
                        "camera_id": camera_id,
                        "resolution_values": sorted(f"{width}x{height}" for width, height in resolution_values),
                    },
                )
            )

    quality_samples: list[QualitySample] = []
    if sample_frames_per_asset > 0:
        for asset in assets:
            quality_samples.extend(_sample_video_asset_quality(asset, sample_frames_per_asset))

    summary = {
        "asset_count": len(assets),
        "camera_count": len(per_camera_assets),
        "total_duration_s": round(total_duration_s, 3),
        "fps_distribution": dict(fps_counter),
        "resolution_distribution": dict(resolution_counter),
        "codec_distribution": dict(codec_counter),
        "missing_creation_time_count": missing_creation_time_count,
        "zero_geometry_count": zero_geometry_count,
        "zero_fps_count": zero_fps_count,
        "zero_frame_count": zero_frame_count,
        "quality_summary": _summarize_quality_samples(quality_samples),
        "camera_inventory_coverage": _inventory_coverage_summary(set(per_camera_assets), inventory_by_id),
    }
    per_camera = {
        camera_id: {
            "asset_count": len(camera_assets),
            "total_duration_s": round(sum(float(asset.duration_s) for asset in camera_assets), 3),
            "fps_values": sorted({_format_number(asset.fps) for asset in camera_assets}),
            "resolutions": sorted({f"{asset.width}x{asset.height}" for asset in camera_assets}),
            "codecs": sorted({str(asset.codec_name or 'unknown') for asset in camera_assets}),
            "role": inventory_by_id[camera_id].role if camera_id in inventory_by_id else None,
            "installation_id": inventory_by_id[camera_id].installation_id if camera_id in inventory_by_id else None,
            "safe_zone_ref": inventory_by_id[camera_id].safe_zone_ref if camera_id in inventory_by_id else None,
            "stream_uri_ref": inventory_by_id[camera_id].stream_uri_ref if camera_id in inventory_by_id else None,
        }
        for camera_id, camera_assets in sorted(per_camera_assets.items())
    }
    return DataAuditReport(
        source_type="video_assets",
        asset_count=len(assets),
        camera_count=len(per_camera_assets),
        summary=summary,
        per_camera=per_camera,
        issues=issues,
        quality_samples=quality_samples,
        metadata={"sample_frames_per_asset": sample_frames_per_asset},
    )


def audit_replay_manifest(
    manifest_path: str | Path,
    *,
    inspect_images: bool = False,
    max_inspected_frames: int | None = None,
    camera_inventory: list[CameraInventoryRecord] | None = None,
    calibration_registry: list[CalibrationRegistryRecord] | None = None,
) -> DataAuditReport:
    reader = ReplayManifestReader(manifest_path)
    packets = reader.read_packets()
    per_camera_packets: dict[str, list[Any]] = defaultdict(list)
    inventory_by_id = camera_inventory_by_id(camera_inventory or [])
    calibration_by_ref = calibration_registry_by_ref(calibration_registry or [])
    sync_counter = Counter()
    quality_present_count = 0
    missing_image_count = 0
    issues: list[AuditIssue] = []
    quality_samples: list[QualitySample] = []

    for packet in packets:
        per_camera_packets[packet.camera_id].append(packet)
        sync_counter[packet.sync_status.value] += 1
        if packet.metadata.get("quality_score") is not None:
            quality_present_count += 1
        if not Path(packet.image_ref).exists():
            missing_image_count += 1
            issues.append(
                AuditIssue(
                    severity="warning",
                    code="missing_image_ref",
                    message="Replay packet image_ref does not exist.",
                    context={"frame_id": packet.frame_id, "image_ref": packet.image_ref},
                )
            )
        camera_record = inventory_by_id.get(packet.camera_id)
        if camera_record is None:
            issues.append(
                AuditIssue(
                    severity="warning",
                    code="missing_camera_inventory",
                    message="Replay packet camera is not present in camera inventory.",
                    context={"camera_id": packet.camera_id, "frame_id": packet.frame_id},
                )
            )
        else:
            if not camera_record.installation_id:
                issues.append(
                    AuditIssue(
                        severity="warning",
                        code="missing_installation_id",
                        message="Camera inventory entry has no installation_id.",
                        context={"camera_id": packet.camera_id},
                    )
                )
            if camera_record.calibration_ref is None:
                issues.append(
                    AuditIssue(
                        severity="warning",
                        code="missing_calibration_ref",
                        message="Camera inventory entry has no calibration_ref.",
                        context={"camera_id": packet.camera_id},
                    )
                )
            elif calibration_by_ref and camera_record.calibration_ref not in calibration_by_ref:
                issues.append(
                    AuditIssue(
                        severity="warning",
                        code="missing_calibration_registry_entry",
                        message="calibration_ref is missing from calibration registry.",
                        context={"camera_id": packet.camera_id, "calibration_ref": camera_record.calibration_ref},
                    )
                )
            if camera_record.role in {"primary", "verification"} and not camera_record.safe_zone_ref:
                issues.append(
                    AuditIssue(
                        severity="warning",
                        code="missing_safe_zone_ref",
                        message="Actionable camera inventory entry has no safe_zone_ref.",
                        context={"camera_id": packet.camera_id, "role": camera_record.role},
                    )
                )
            if source_type_requires_stream_ref(camera_record.source_type) and not camera_record.stream_uri_ref:
                issues.append(
                    AuditIssue(
                        severity="warning",
                        code="missing_stream_uri_ref",
                        message="Live camera inventory entry has no stream_uri_ref.",
                        context={"camera_id": packet.camera_id, "source_type": camera_record.source_type},
                    )
                )
            if camera_record.mount_height_m is not None and float(camera_record.mount_height_m) <= 0.0:
                issues.append(
                    AuditIssue(
                        severity="warning",
                        code="invalid_mount_height",
                        message="mount_height_m must be positive when provided.",
                        context={"camera_id": packet.camera_id, "mount_height_m": camera_record.mount_height_m},
                    )
                )
            if camera_record.view_direction_deg is not None:
                view_direction = float(camera_record.view_direction_deg)
                if not 0.0 <= view_direction < 360.0:
                    issues.append(
                        AuditIssue(
                            severity="warning",
                            code="invalid_view_direction",
                            message="view_direction_deg must be in [0, 360).",
                            context={"camera_id": packet.camera_id, "view_direction_deg": camera_record.view_direction_deg},
                        )
                    )

    inspected_count = 0
    if inspect_images:
        for packet in packets:
            if max_inspected_frames is not None and inspected_count >= max_inspected_frames:
                break
            image_path = Path(packet.image_ref)
            if not image_path.exists():
                continue
            quality_samples.append(_compute_quality_sample_from_image(image_path, packet.camera_id, packet.timestamp))
            inspected_count += 1

    per_camera = {}
    for camera_id, camera_packets in sorted(per_camera_packets.items()):
        timestamps = [packet.timestamp for packet in camera_packets]
        timestamp_gaps = [
            round(camera_packets[index + 1].timestamp - camera_packets[index].timestamp, 6)
            for index in range(len(camera_packets) - 1)
        ]
        per_camera[camera_id] = {
            "frame_count": len(camera_packets),
            "time_span_s": round((max(timestamps) - min(timestamps)) if len(timestamps) >= 2 else 0.0, 6),
            "avg_inter_frame_gap_s": round(sum(timestamp_gaps) / len(timestamp_gaps), 6) if timestamp_gaps else None,
            "quality_score_present_count": sum(
                1 for packet in camera_packets if packet.metadata.get("quality_score") is not None
            ),
            "sync_status_distribution": dict(Counter(packet.sync_status.value for packet in camera_packets)),
            "role": inventory_by_id[camera_id].role if camera_id in inventory_by_id else None,
            "installation_id": inventory_by_id[camera_id].installation_id if camera_id in inventory_by_id else None,
            "safe_zone_ref": inventory_by_id[camera_id].safe_zone_ref if camera_id in inventory_by_id else None,
            "stream_uri_ref": inventory_by_id[camera_id].stream_uri_ref if camera_id in inventory_by_id else None,
        }

    summary = {
        "packet_count": len(packets),
        "camera_count": len(per_camera_packets),
        "sync_status_distribution": dict(sync_counter),
        "quality_score_present_count": quality_present_count,
        "missing_image_count": missing_image_count,
        "quality_summary": _summarize_quality_samples(quality_samples),
        "camera_inventory_coverage": _inventory_coverage_summary(set(per_camera_packets), inventory_by_id),
    }
    return DataAuditReport(
        source_type="replay_manifest",
        asset_count=len(packets),
        camera_count=len(per_camera_packets),
        summary=summary,
        per_camera=per_camera,
        issues=issues,
        quality_samples=quality_samples,
        metadata={
            "manifest_path": str(manifest_path),
            "inspect_images": inspect_images,
            "max_inspected_frames": max_inspected_frames,
        },
    )


def format_audit_report(report: DataAuditReport) -> str:
    lines = [
        f"source_type={report.source_type}",
        f"asset_count={report.asset_count}",
        f"camera_count={report.camera_count}",
        f"issue_count={len(report.issues)}",
    ]
    quality_summary = report.summary.get("quality_summary") or {}
    if quality_summary:
        lines.append(f"quality_sample_count={quality_summary.get('sample_count', 0)}")
    for key in ("fps_distribution", "resolution_distribution", "codec_distribution", "sync_status_distribution"):
        value = report.summary.get(key)
        if value:
            lines.append(f"{key}={json.dumps(value, ensure_ascii=True, sort_keys=True)}")
    return "\n".join(lines)


def _sample_video_asset_quality(asset: VideoAsset, sample_frames_per_asset: int) -> list[QualitySample]:
    if sample_frames_per_asset <= 0 or asset.duration_s <= 0.0:
        return []
    timestamps = _sample_timestamps(asset.duration_s, sample_frames_per_asset)
    quality_samples: list[QualitySample] = []
    for timestamp_s in timestamps:
        image = _extract_video_frame(asset.source_path, timestamp_s)
        if image is None:
            continue
        quality_samples.append(_compute_quality_sample_from_array(image.array, asset.source_path, asset.camera_id, timestamp_s))
    return quality_samples


def _sample_timestamps(duration_s: float, sample_count: int) -> list[float]:
    if sample_count <= 1:
        return [max(0.0, duration_s / 2.0)]
    step = duration_s / float(sample_count + 1)
    return [round(step * float(index + 1), 3) for index in range(sample_count)]


def _extract_video_frame(video_path: str | Path, timestamp_s: float) -> Any | None:
    command = [
        "ffmpeg",
        "-loglevel",
        "error",
        "-ss",
        f"{timestamp_s:.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-f",
        "image2pipe",
        "-vcodec",
        "png",
        "-",
    ]
    completed = subprocess.run(command, capture_output=True, text=False)
    if completed.returncode != 0 or not completed.stdout:
        return None
    with Image.open(BytesIO(completed.stdout)) as frame:
        rgb_frame = frame.convert("RGB")
        return type(
            "AuditLoadedFrame",
            (),
            {
                "array": np.asarray(rgb_frame),
                "width": rgb_frame.width,
                "height": rgb_frame.height,
            },
        )()


def _compute_quality_sample_from_image(image_path: Path, camera_id: str, timestamp_s: float | None) -> QualitySample:
    image = load_rgb_image(image_path)
    return _compute_quality_sample_from_array(image.array, str(image_path), camera_id, timestamp_s)


def _compute_quality_sample_from_array(
    array: np.ndarray,
    source_ref: str,
    camera_id: str,
    timestamp_s: float | None,
) -> QualitySample:
    grayscale = array.mean(axis=2) if array.ndim == 3 else array
    normalized_gray = np.asarray(grayscale, dtype=np.float32) / 255.0
    vertical_edges = np.abs(np.diff(normalized_gray, axis=0)).mean() if normalized_gray.shape[0] > 1 else 0.0
    horizontal_edges = np.abs(np.diff(normalized_gray, axis=1)).mean() if normalized_gray.shape[1] > 1 else 0.0
    sharpness_score = float(min(1.0, (vertical_edges + horizontal_edges) * 3.0))
    return QualitySample(
        source_ref=source_ref,
        camera_id=camera_id,
        timestamp_s=timestamp_s,
        brightness_mean=normalized_grayscale_mean(array),
        contrast_score=normalized_grayscale_std(array),
        sharpness_score=sharpness_score,
        dark_clipped_ratio=float((normalized_gray <= 0.02).mean()),
        bright_clipped_ratio=float((normalized_gray >= 0.98).mean()),
        width=int(array.shape[1]),
        height=int(array.shape[0]),
    )


def _summarize_quality_samples(samples: list[QualitySample]) -> dict[str, Any]:
    if not samples:
        return {}
    return {
        "sample_count": len(samples),
        "brightness_mean": _summarize_numbers([sample.brightness_mean for sample in samples]),
        "contrast_score": _summarize_numbers([sample.contrast_score for sample in samples]),
        "sharpness_score": _summarize_numbers([sample.sharpness_score for sample in samples]),
        "dark_clipped_ratio": _summarize_numbers([sample.dark_clipped_ratio for sample in samples]),
        "bright_clipped_ratio": _summarize_numbers([sample.bright_clipped_ratio for sample in samples]),
    }


def _summarize_numbers(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    return {
        "avg": round(sum(values) / len(values), 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
    }


def _format_number(value: float) -> str:
    return f"{float(value):.3f}"


def _inventory_coverage_summary(
    observed_camera_ids: set[str],
    inventory_by_id: dict[str, CameraInventoryRecord],
) -> dict[str, Any]:
    if not observed_camera_ids:
        return {}
    covered = sorted(camera_id for camera_id in observed_camera_ids if camera_id in inventory_by_id)
    missing = sorted(camera_id for camera_id in observed_camera_ids if camera_id not in inventory_by_id)
    return {
        "observed_camera_count": len(observed_camera_ids),
        "covered_camera_count": len(covered),
        "missing_camera_count": len(missing),
        "covered_camera_ids": covered,
        "missing_camera_ids": missing,
    }
