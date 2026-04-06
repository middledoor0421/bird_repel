from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import random
from typing import Any

from thesis3.core import stable_hash


class StressProfile:
    def __init__(
        self,
        *,
        name: str,
        drop_probability: float = 0.0,
        camera_drop_probabilities: dict[str, float] | None = None,
        timestamp_jitter_ms: float = 0.0,
        mark_unsynced_probability: float = 0.0,
        mark_estimated_probability: float = 0.0,
        quality_score_scale: float = 1.0,
        detector_score_scale: float = 1.0,
        verification_score_scale: float = 1.0,
        detector_latency_scale: float = 1.0,
        verification_latency_scale: float = 1.0,
        bbox_noise_px: float = 0.0,
    ) -> None:
        self.name = name
        self.drop_probability = float(drop_probability)
        self.camera_drop_probabilities = dict(camera_drop_probabilities or {})
        self.timestamp_jitter_ms = float(timestamp_jitter_ms)
        self.mark_unsynced_probability = float(mark_unsynced_probability)
        self.mark_estimated_probability = float(mark_estimated_probability)
        self.quality_score_scale = float(quality_score_scale)
        self.detector_score_scale = float(detector_score_scale)
        self.verification_score_scale = float(verification_score_scale)
        self.detector_latency_scale = float(detector_latency_scale)
        self.verification_latency_scale = float(verification_latency_scale)
        self.bbox_noise_px = float(bbox_noise_px)


PRESET_STRESS_PROFILES: dict[str, StressProfile] = {
    "sync_jitter": StressProfile(
        name="sync_jitter",
        timestamp_jitter_ms=18.0,
        mark_unsynced_probability=0.35,
    ),
    "quality_drop": StressProfile(
        name="quality_drop",
        quality_score_scale=0.45,
        detector_score_scale=0.85,
        verification_score_scale=0.70,
        bbox_noise_px=4.0,
    ),
    "camera_dropout": StressProfile(
        name="camera_dropout",
        camera_drop_probabilities={"cam_tele": 0.4},
    ),
    "latency_spike": StressProfile(
        name="latency_spike",
        detector_latency_scale=2.5,
        verification_latency_scale=3.0,
        mark_estimated_probability=0.2,
    ),
    "mixed_faults": StressProfile(
        name="mixed_faults",
        camera_drop_probabilities={"cam_tele": 0.25},
        timestamp_jitter_ms=12.0,
        mark_unsynced_probability=0.25,
        quality_score_scale=0.60,
        detector_score_scale=0.9,
        verification_score_scale=0.75,
        detector_latency_scale=1.8,
        verification_latency_scale=2.2,
        bbox_noise_px=3.0,
    ),
}


def load_manifest_records(path: str | Path) -> list[dict[str, Any]]:
    manifest_path = Path(path)
    if manifest_path.suffix.lower() == ".jsonl":
        return [
            json.loads(line)
            for line in manifest_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    if manifest_path.suffix.lower() == ".json":
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("JSON replay manifest must contain a list.")
        return payload
    raise ValueError(f"Unsupported manifest format: {manifest_path.suffix}")


def write_manifest_records(records: list[dict[str, Any]], output_path: str | Path) -> Path:
    manifest_path = Path(output_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")
    return manifest_path


def generate_stress_variant(
    records: list[dict[str, Any]],
    profile: StressProfile,
    *,
    seed: int = 0,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    stressed_records: list[dict[str, Any]] = []
    for raw_record in records:
        record = deepcopy(raw_record)
        camera_id = str(record.get("camera_id", "unknown"))
        if _should_drop_frame(profile, camera_id, rng):
            continue
        record["timestamp"] = round(float(record.get("timestamp", 0.0)) + _jitter_seconds(profile, rng), 6)
        record["sync_status"] = _resolve_sync_status(record.get("sync_status"), profile, rng)
        metadata = dict(record.get("metadata", {}))
        if "quality_score" in metadata:
            metadata["quality_score"] = _scale_score(metadata.get("quality_score"), profile.quality_score_scale)
        if "detector_latency_ms" in metadata:
            metadata["detector_latency_ms"] = _scale_latency(metadata.get("detector_latency_ms"), profile.detector_latency_scale)
        if "verification_latency_ms" in metadata:
            metadata["verification_latency_ms"] = _scale_latency(
                metadata.get("verification_latency_ms"),
                profile.verification_latency_scale,
            )
        if "verification_score" in metadata:
            metadata["verification_score"] = _scale_score(
                metadata.get("verification_score"),
                profile.verification_score_scale,
            )
        detections = []
        for raw_detection in metadata.get("detections", []):
            detection = dict(raw_detection)
            if "score" in detection:
                detection["score"] = _scale_score(detection.get("score"), profile.detector_score_scale)
            if "bbox" in detection:
                detection["bbox"] = _perturb_bbox(detection["bbox"], profile.bbox_noise_px, rng)
            detections.append(detection)
        if detections:
            metadata["detections"] = detections
        metadata["stress_profile"] = profile.name
        metadata["stress_seed"] = seed
        metadata["stress_record_id"] = stable_hash({"frame_id": record.get("frame_id"), "profile": profile.name, "seed": seed})
        record["metadata"] = metadata
        stressed_records.append(record)
    return sorted(stressed_records, key=lambda item: float(item.get("timestamp", 0.0)))


def generate_preset_variants(
    input_manifest_path: str | Path,
    *,
    output_dir: str | Path,
    preset_names: list[str],
    seed: int = 0,
) -> dict[str, str]:
    input_records = load_manifest_records(input_manifest_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}
    for index, preset_name in enumerate(preset_names):
        if preset_name not in PRESET_STRESS_PROFILES:
            raise KeyError(f"Unknown stress preset: {preset_name}")
        profile = PRESET_STRESS_PROFILES[preset_name]
        stressed = generate_stress_variant(input_records, profile, seed=seed + index)
        output_path = output_root / f"{preset_name}.jsonl"
        write_manifest_records(stressed, output_path)
        written[preset_name] = str(output_path)
    return written


def _should_drop_frame(profile: StressProfile, camera_id: str, rng: random.Random) -> bool:
    drop_probability = profile.camera_drop_probabilities.get(camera_id, profile.drop_probability)
    return rng.random() < drop_probability


def _jitter_seconds(profile: StressProfile, rng: random.Random) -> float:
    if profile.timestamp_jitter_ms <= 0.0:
        return 0.0
    return rng.uniform(-profile.timestamp_jitter_ms, profile.timestamp_jitter_ms) / 1000.0


def _resolve_sync_status(raw_value: Any, profile: StressProfile, rng: random.Random) -> str:
    if rng.random() < profile.mark_unsynced_probability:
        return "unsynced"
    if rng.random() < profile.mark_estimated_probability:
        return "estimated"
    return str(raw_value or "synced")


def _scale_score(raw_value: Any, scale: float) -> float:
    value = float(raw_value)
    return round(max(0.0, min(1.0, value * scale)), 6)


def _scale_latency(raw_value: Any, scale: float) -> float:
    value = float(raw_value)
    return round(max(0.0, value * scale), 6)


def _perturb_bbox(raw_bbox: Any, noise_px: float, rng: random.Random) -> list[float]:
    values = [float(value) for value in raw_bbox]
    if noise_px <= 0.0 or len(values) != 4:
        return values
    dx1 = rng.uniform(-noise_px, noise_px)
    dy1 = rng.uniform(-noise_px, noise_px)
    dx2 = rng.uniform(-noise_px, noise_px)
    dy2 = rng.uniform(-noise_px, noise_px)
    x1 = max(0.0, values[0] + dx1)
    y1 = max(0.0, values[1] + dy1)
    x2 = max(x1 + 1.0, values[2] + dx2)
    y2 = max(y1 + 1.0, values[3] + dy2)
    return [round(x1, 3), round(y1, 3), round(x2, 3), round(y2, 3)]
