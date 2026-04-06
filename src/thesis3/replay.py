from __future__ import annotations

import json
from pathlib import Path

from thesis3.core import FramePacket, SyncStatus


class ReplayManifestReader:
    def __init__(self, manifest_path: str | Path) -> None:
        self.manifest_path = Path(manifest_path)

    def read_packets(self) -> list[FramePacket]:
        if self.manifest_path.suffix.lower() == ".jsonl":
            raw_items = [
                json.loads(line)
                for line in self.manifest_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        elif self.manifest_path.suffix.lower() == ".json":
            raw_items = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        else:
            raise ValueError(f"Unsupported manifest format: {self.manifest_path.suffix}")

        packets = [self._parse_packet(item) for item in raw_items]
        return sorted(packets, key=lambda packet: packet.timestamp)

    def _parse_packet(self, raw: dict) -> FramePacket:
        metadata = dict(raw.get("metadata", {}))
        if "detections" in raw and "detections" not in metadata:
            metadata["detections"] = raw["detections"]
        sync_status = SyncStatus(raw.get("sync_status", SyncStatus.SYNCED.value))
        return FramePacket(
            frame_id=raw["frame_id"],
            camera_id=raw["camera_id"],
            timestamp=float(raw["timestamp"]),
            image_ref=raw["image_ref"],
            metadata=metadata,
            sync_status=sync_status,
        )


def group_packets_by_timestamp(
    packets: list[FramePacket], tolerance_ms: int
) -> list[list[FramePacket]]:
    if not packets:
        return []

    groups: list[list[FramePacket]] = []
    tolerance_seconds = tolerance_ms / 1000.0
    current_group = [packets[0]]

    for packet in packets[1:]:
        group_anchor = current_group[0].timestamp
        if packet.timestamp - group_anchor <= tolerance_seconds:
            current_group.append(packet)
            continue
        groups.append(current_group)
        current_group = [packet]

    groups.append(current_group)
    return groups
