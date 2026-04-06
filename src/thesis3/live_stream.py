from __future__ import annotations

import heapq
from pathlib import Path
import subprocess
import time
from typing import Any, Iterator

import numpy as np
from PIL import Image

from thesis3.core import FramePacket, stable_hash
from thesis3.dataclass_compat import dataclass


@dataclass(slots=True)
class LiveSourceSpec:
    camera_id: str
    uri: str
    sample_fps: float
    timestamp_offset_s: float = 0.0
    realtime: bool = False
    scale_width: int | None = None
    rtsp_transport: str = "tcp"
    timestamp_mode: str = "media_time"


@dataclass(slots=True)
class LiveExecutionConfig:
    sources: list[LiveSourceSpec]
    spool_dir: str
    frame_format: str = "jpg"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LiveExecutionConfig":
        source_specs = [LiveSourceSpec(**source) for source in payload.get("sources", [])]
        if not source_specs:
            raise ValueError("Live config requires at least one source.")
        return cls(
            sources=source_specs,
            spool_dir=str(payload.get("spool_dir", "artifacts/live_spool")),
            frame_format=str(payload.get("frame_format", "jpg")),
        )


class FfmpegFrameSource:
    def __init__(self, spec: LiveSourceSpec, spool_dir: str | Path, frame_format: str = "jpg") -> None:
        if spec.sample_fps <= 0.0:
            raise ValueError("sample_fps must be positive for live sources.")
        self.spec = spec
        self.frame_format = frame_format
        self._source_token = stable_hash({"camera_id": spec.camera_id, "uri": spec.uri})
        self._spool_dir = Path(spool_dir) / spec.camera_id
        self._spool_dir.mkdir(parents=True, exist_ok=True)
        self._process: subprocess.Popen[bytes] | None = None
        self._frame_index = 0
        self._start_monotonic = time.monotonic()
        self._output_width, self._output_height = self._resolve_output_geometry()
        self._frame_size_bytes = self._output_width * self._output_height * 3

    def start(self) -> None:
        if self._process is not None:
            return
        command = self._build_ffmpeg_command()
        self._process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

    def close(self) -> None:
        if self._process is None:
            return
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=2.0)
        self._process = None

    def next_packet(self) -> FramePacket | None:
        self.start()
        if self._process is None or self._process.stdout is None:
            return None

        frame_bytes = self._read_exact(self._frame_size_bytes)
        if frame_bytes is None:
            self.close()
            return None

        frame_array = np.frombuffer(frame_bytes, dtype=np.uint8).reshape(
            (self._output_height, self._output_width, 3)
        )
        image_path = self._write_frame_image(frame_array)
        timestamp_s = self._timestamp_for_frame(self._frame_index)
        packet = FramePacket(
            frame_id=f"{self.spec.camera_id}-{self._source_token}-{self._frame_index:06d}",
            camera_id=self.spec.camera_id,
            timestamp=timestamp_s,
            image_ref=str(image_path),
            metadata={
                "source_uri": self.spec.uri,
                "source_type": "live_stream",
                "frame_index": self._frame_index,
                "sample_fps": self.spec.sample_fps,
                "timestamp_mode": self.spec.timestamp_mode,
                "capture_wall_time_s": time.time(),
            },
        )
        self._frame_index += 1
        return packet

    def _read_exact(self, size: int) -> bytes | None:
        if self._process is None or self._process.stdout is None:
            return None

        chunks = bytearray()
        while len(chunks) < size:
            chunk = self._process.stdout.read(size - len(chunks))
            if not chunk:
                return None if len(chunks) == 0 else bytes(chunks)
            chunks.extend(chunk)
        if len(chunks) != size:
            return None
        return bytes(chunks)

    def _write_frame_image(self, frame_array: np.ndarray) -> Path:
        image_path = self._spool_dir / f"{self.spec.camera_id}_{self._frame_index:06d}.{self.frame_format}"
        Image.fromarray(frame_array, mode="RGB").save(image_path)
        return image_path

    def _timestamp_for_frame(self, frame_index: int) -> float:
        if self.spec.timestamp_mode == "wallclock":
            elapsed = time.monotonic() - self._start_monotonic
            return self.spec.timestamp_offset_s + elapsed
        return self.spec.timestamp_offset_s + (frame_index / self.spec.sample_fps)

    def _build_ffmpeg_command(self) -> list[str]:
        filter_terms = [f"fps={self.spec.sample_fps}"]
        if self.spec.scale_width is not None and self.spec.scale_width > 0:
            filter_terms.append(f"scale={self._output_width}:{self._output_height}")

        command = ["ffmpeg", "-loglevel", "error"]
        if self.spec.realtime:
            command.append("-re")
        if self.spec.uri.startswith("rtsp://"):
            command.extend(["-rtsp_transport", self.spec.rtsp_transport])
        command.extend(
            [
                "-i",
                self.spec.uri,
                "-vf",
                ",".join(filter_terms),
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "-",
            ]
        )
        return command

    def _resolve_output_geometry(self) -> tuple[int, int]:
        source_width, source_height = probe_stream_geometry(self.spec.uri)
        if self.spec.scale_width is None or self.spec.scale_width <= 0:
            return source_width, source_height
        scaled_height = int(round((source_height * self.spec.scale_width) / source_width))
        if scaled_height % 2 == 1:
            scaled_height += 1
        return self.spec.scale_width, max(2, scaled_height)


def probe_stream_geometry(uri: str) -> tuple[int, int]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        uri,
    ]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    values = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if len(values) < 2:
        raise ValueError(f"Unable to probe geometry for stream: {uri}")
    return int(values[0]), int(values[1])


def iter_live_packet_groups(
    sources: list[FfmpegFrameSource],
    tolerance_ms: int,
    max_groups: int | None = None,
    max_seconds: float | None = None,
) -> Iterator[list[FramePacket]]:
    tolerance_s = tolerance_ms / 1000.0
    started_at = time.monotonic()
    heap: list[tuple[float, int, FramePacket]] = []

    for source_index, source in enumerate(sources):
        packet = source.next_packet()
        if packet is not None:
            heapq.heappush(heap, (packet.timestamp, source_index, packet))

    group_count = 0
    try:
        while heap:
            if max_groups is not None and group_count >= max_groups:
                break
            if max_seconds is not None and (time.monotonic() - started_at) >= max_seconds:
                break

            anchor_timestamp, source_index, packet = heapq.heappop(heap)
            group = [packet]
            consumed_source_indices = [source_index]

            while heap and (heap[0][0] - anchor_timestamp) <= tolerance_s:
                _, extra_source_index, extra_packet = heapq.heappop(heap)
                group.append(extra_packet)
                consumed_source_indices.append(extra_source_index)

            for consumed_source_index in consumed_source_indices:
                next_packet = sources[consumed_source_index].next_packet()
                if next_packet is not None:
                    heapq.heappush(heap, (next_packet.timestamp, consumed_source_index, next_packet))

            yield sorted(group, key=lambda item: item.timestamp)
            group_count += 1
    finally:
        for source in sources:
            source.close()
