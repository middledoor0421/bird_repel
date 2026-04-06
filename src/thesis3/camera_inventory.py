from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from thesis3.dataclass_compat import dataclass, field
from thesis3.video_data import VideoAsset, write_jsonl


@dataclass(slots=True)
class CameraInventoryRecord:
    camera_id: str
    role: str = "unknown"
    site_id: str = "default_site"
    installation_id: str | None = None
    environment_tag: str = "unknown"
    timezone: str | None = None
    source_type: str = "unknown"
    calibration_ref: str | None = None
    safe_zone_ref: str | None = None
    stream_uri_ref: str | None = None
    mount_height_m: float | None = None
    view_direction_deg: float | None = None
    is_ptz: bool = False
    expected_fps: float | None = None
    expected_width: int | None = None
    expected_height: int | None = None
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CalibrationRegistryRecord:
    calibration_ref: str
    camera_id: str
    calibration_type: str = "unknown"
    file_ref: str | None = None
    version: str | None = None
    valid_from: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def load_camera_inventory(path: str | Path) -> list[CameraInventoryRecord]:
    return [CameraInventoryRecord(**record) for record in _read_json_records(path)]


def load_calibration_registry(path: str | Path) -> list[CalibrationRegistryRecord]:
    return [CalibrationRegistryRecord(**record) for record in _read_json_records(path)]


def camera_inventory_by_id(records: list[CameraInventoryRecord]) -> dict[str, CameraInventoryRecord]:
    return {record.camera_id: record for record in records}


def calibration_registry_by_ref(records: list[CalibrationRegistryRecord]) -> dict[str, CalibrationRegistryRecord]:
    return {record.calibration_ref: record for record in records}


def build_camera_inventory_from_assets(
    assets: list[VideoAsset],
    *,
    default_site_id: str = "default_site",
    default_environment_tag: str = "unknown",
    default_timezone: str | None = None,
    stream_ref_prefix: str = "stream_ref::",
    safe_zone_ref_prefix: str = "safe_zone::",
) -> list[CameraInventoryRecord]:
    grouped: dict[str, list[VideoAsset]] = {}
    for asset in assets:
        grouped.setdefault(asset.camera_id, []).append(asset)

    inventory: list[CameraInventoryRecord] = []
    for camera_id, camera_assets in sorted(grouped.items()):
        representative = sorted(camera_assets, key=lambda asset: (asset.width * asset.height, asset.fps), reverse=True)[0]
        source_types = sorted({str(asset.metadata.get("source_type", "mp4")) for asset in camera_assets})
        role = infer_camera_role(camera_id)
        inventory.append(
            CameraInventoryRecord(
                camera_id=camera_id,
                role=role,
                site_id=default_site_id,
                installation_id=f"{default_site_id}:{camera_id}:mount-v1",
                environment_tag=default_environment_tag,
                timezone=default_timezone,
                source_type=source_types[0] if len(source_types) == 1 else "mixed",
                calibration_ref=f"{camera_id}-calibration-v1",
                safe_zone_ref=f"{safe_zone_ref_prefix}{default_site_id}/{camera_id}",
                stream_uri_ref=f"{stream_ref_prefix}{default_site_id}/{camera_id}",
                mount_height_m=None,
                view_direction_deg=None,
                is_ptz=role == "verification",
                expected_fps=float(representative.fps) if representative.fps > 0 else None,
                expected_width=int(representative.width) if representative.width > 0 else None,
                expected_height=int(representative.height) if representative.height > 0 else None,
                metadata={
                    "asset_count": len(camera_assets),
                    "source_paths": [asset.source_path for asset in camera_assets],
                    "codec_names": sorted({str(asset.codec_name or 'unknown') for asset in camera_assets}),
                },
            )
        )
    return inventory


def build_calibration_registry_template(
    inventory: list[CameraInventoryRecord],
) -> list[CalibrationRegistryRecord]:
    return [
        CalibrationRegistryRecord(
            calibration_ref=record.calibration_ref or f"{record.camera_id}-calibration-v1",
            camera_id=record.camera_id,
            calibration_type="unknown",
            file_ref=None,
            version="v1",
            valid_from=None,
            metadata={
                "status": "template",
                "notes": "Fill calibration path and metadata once field calibration is available.",
            },
        )
        for record in inventory
    ]


def export_camera_setup(
    *,
    inventory: list[CameraInventoryRecord],
    calibration_registry: list[CalibrationRegistryRecord] | None = None,
    output_dir: str | Path,
) -> dict[str, str]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}
    inventory_path = output_root / "camera_inventory.jsonl"
    write_jsonl(inventory, inventory_path)
    written["camera_inventory"] = str(inventory_path)
    if calibration_registry is not None:
        calibration_path = output_root / "calibration_registry.jsonl"
        write_jsonl(calibration_registry, calibration_path)
        written["calibration_registry"] = str(calibration_path)
    return written


def infer_camera_role(camera_id: str) -> str:
    lowered = camera_id.lower()
    if any(token in lowered for token in ("wide", "primary", "central")):
        return "primary"
    if any(token in lowered for token in ("tele", "zoom", "verification")):
        return "verification"
    if any(token in lowered for token in ("overview", "context")):
        return "overview"
    return "unknown"


def source_type_requires_stream_ref(source_type: str) -> bool:
    lowered = source_type.lower().strip()
    return lowered not in {"", "unknown", "mp4", "file", "offline"}


def _read_json_records(path: str | Path) -> list[dict[str, Any]]:
    input_path = Path(path)
    if input_path.suffix.lower() == ".jsonl":
        return [
            json.loads(line)
            for line in input_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected list payload: {input_path}")
    return payload
