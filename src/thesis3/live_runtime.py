from __future__ import annotations

from pathlib import Path
from typing import Any

from thesis3.pipelines import build_pipeline
from thesis3.live_stream import FfmpegFrameSource, LiveExecutionConfig, iter_live_packet_groups
from thesis3.runtime import build_runtime


def execute_live_stream(
    config_path: str | Path,
    max_groups: int | None = None,
    max_seconds: float | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    runtime = build_runtime(config_path)
    live_payload = runtime.config.extra.get("live")
    if not isinstance(live_payload, dict):
        raise ValueError("Live execution requires config.extra.live to be defined.")

    live_config = LiveExecutionConfig.from_dict(live_payload)
    sources = [
        FfmpegFrameSource(
            spec=source_spec,
            spool_dir=live_config.spool_dir,
            frame_format=live_config.frame_format,
        )
        for source_spec in live_config.sources
    ]

    pipeline = build_pipeline(runtime)
    runtime.log(
        "live_run_start",
        {
            "run_id": runtime.run_id,
            "source_count": len(sources),
            "source_camera_ids": [source.spec.camera_id for source in sources],
            "spool_dir": live_config.spool_dir,
        },
    )

    decisions = []
    group_count = 0
    for group in iter_live_packet_groups(
        sources=sources,
        tolerance_ms=runtime.config.replay.timestamp_tolerance_ms,
        max_groups=max_groups,
        max_seconds=max_seconds,
    ):
        runtime.log(
            "live_group_ingested",
            {
                "group_index": group_count,
                "packet_count": len(group),
                "camera_ids": [packet.camera_id for packet in group],
                "timestamps": [packet.timestamp for packet in group],
            },
            timestamp=group[0].timestamp if group else None,
        )
        decisions.extend(pipeline.process_group(group))
        group_count += 1

    runtime.log(
        "run_complete",
        {
            "run_id": runtime.run_id,
            "decision_count": len(decisions),
            "group_count": group_count,
            "mode": "live_stream",
        },
    )
    return str(runtime.event_store.path), [decision.stage1_summary for decision in decisions]
