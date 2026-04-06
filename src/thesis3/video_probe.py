from __future__ import annotations

from fractions import Fraction
import json
from pathlib import Path
import subprocess

from thesis3.video_data import VideoAsset, build_asset_id, infer_camera_id


def scan_mp4_files(input_root: str | Path) -> list[Path]:
    root = Path(input_root)
    if root.is_file():
        return [root] if root.suffix.lower() == ".mp4" else []
    return sorted(path for path in root.rglob("*.mp4") if path.is_file())


def probe_mp4_asset(path: str | Path, camera_strategy: str = "parent") -> VideoAsset:
    video_path = Path(path).resolve()
    ffprobe_payload = _run_ffprobe(video_path)
    stream = _select_video_stream(ffprobe_payload)
    format_payload = ffprobe_payload.get("format", {})

    duration_s = float(format_payload.get("duration") or stream.get("duration") or 0.0)
    fps = _parse_fps(stream.get("avg_frame_rate") or stream.get("r_frame_rate"))
    frame_count = int(stream.get("nb_frames") or round(duration_s * fps) or 0)
    camera_id = infer_camera_id(video_path, strategy=camera_strategy)
    metadata = {
        "relative_path": video_path.name,
        "pix_fmt": stream.get("pix_fmt"),
        "format_name": format_payload.get("format_name"),
    }

    return VideoAsset(
        asset_id=build_asset_id(str(video_path), camera_id),
        source_path=str(video_path),
        camera_id=camera_id,
        width=int(stream.get("width") or 0),
        height=int(stream.get("height") or 0),
        fps=fps,
        duration_s=duration_s,
        frame_count=frame_count,
        codec_name=stream.get("codec_name"),
        file_size_bytes=int(format_payload.get("size")) if format_payload.get("size") else None,
        creation_time=_extract_creation_time(format_payload, stream),
        metadata=metadata,
    )


def index_mp4_corpus(input_root: str | Path, camera_strategy: str = "parent") -> list[VideoAsset]:
    return [probe_mp4_asset(path, camera_strategy=camera_strategy) for path in scan_mp4_files(input_root)]


def _run_ffprobe(video_path: Path) -> dict:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(video_path),
    ]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise ValueError(f"Unexpected ffprobe output for {video_path}")
    return payload


def _select_video_stream(payload: dict) -> dict:
    streams = payload.get("streams", [])
    for stream in streams:
        if stream.get("codec_type") == "video":
            return stream
    raise ValueError("No video stream found in ffprobe payload.")


def _parse_fps(raw_value: str | None) -> float:
    if not raw_value or raw_value == "0/0":
        return 0.0
    return float(Fraction(raw_value))


def _extract_creation_time(format_payload: dict, stream_payload: dict) -> str | None:
    format_tags = format_payload.get("tags", {})
    stream_tags = stream_payload.get("tags", {})
    return format_tags.get("creation_time") or stream_tags.get("creation_time")
