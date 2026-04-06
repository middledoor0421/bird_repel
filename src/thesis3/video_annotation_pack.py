from __future__ import annotations

from html import escape
from pathlib import Path
import subprocess

from thesis3.dataclass_compat import dataclass
from thesis3.video_data import (
    AnnotationLabel,
    ClipTask,
    EventAnnotation,
    load_clip_tasks,
    write_jsonl,
)


@dataclass(slots=True)
class PreviewRecord:
    task_id: str
    asset_id: str
    camera_id: str
    source_path: str
    preview_path: str
    start_time_s: float
    end_time_s: float
    duration_s: float
    tags: list[str]
    metadata: dict


@dataclass(slots=True)
class AnnotationPackSummary:
    output_dir: str
    preview_dir: str
    task_count: int
    preview_count: int
    preview_index_path: str
    annotation_template_path: str
    review_html_path: str


def export_annotation_pack(
    clip_tasks_path: str | Path,
    output_dir: str | Path,
    scale_width: int | None = 640,
    overwrite: bool = False,
    max_tasks: int | None = None,
) -> AnnotationPackSummary:
    tasks = load_clip_tasks(clip_tasks_path)
    if max_tasks is not None:
        tasks = tasks[:max_tasks]

    pack_dir = Path(output_dir)
    preview_dir = pack_dir / "previews"
    pack_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)

    preview_records: list[PreviewRecord] = []
    annotation_template: list[EventAnnotation] = []

    for task in tasks:
        preview_path = preview_dir / f"{task.task_id}.mp4"
        if overwrite or not preview_path.exists():
            export_preview_clip(task=task, output_path=preview_path, scale_width=scale_width)

        preview_record = PreviewRecord(
            task_id=task.task_id,
            asset_id=task.asset_id,
            camera_id=task.camera_id,
            source_path=task.source_path,
            preview_path=str(preview_path),
            start_time_s=task.start_time_s,
            end_time_s=task.end_time_s,
            duration_s=max(0.0, task.end_time_s - task.start_time_s),
            tags=list(task.tags),
            metadata=dict(task.metadata),
        )
        preview_records.append(preview_record)
        annotation_template.append(build_event_annotation_template(task, preview_path))

    preview_index_path = pack_dir / "preview_index.jsonl"
    annotation_template_path = pack_dir / "event_annotations.template.jsonl"
    review_html_path = pack_dir / "review_index.html"

    write_jsonl(preview_records, preview_index_path)
    write_jsonl(annotation_template, annotation_template_path)
    review_html_path.write_text(build_review_html(preview_records, pack_dir), encoding="utf-8")

    return AnnotationPackSummary(
        output_dir=str(pack_dir),
        preview_dir=str(preview_dir),
        task_count=len(tasks),
        preview_count=len(preview_records),
        preview_index_path=str(preview_index_path),
        annotation_template_path=str(annotation_template_path),
        review_html_path=str(review_html_path),
    )


def export_preview_clip(
    task: ClipTask,
    output_path: str | Path,
    scale_width: int | None = 640,
) -> Path:
    preview_path = Path(output_path)
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    duration_s = max(0.0, task.end_time_s - task.start_time_s)
    if duration_s <= 0.0:
        raise ValueError(f"Task duration must be positive: {task.task_id}")

    command = [
        "ffmpeg",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{task.start_time_s:.3f}",
        "-t",
        f"{duration_s:.3f}",
        "-i",
        task.source_path,
    ]
    if scale_width is not None and scale_width > 0:
        command.extend(["-vf", f"scale={scale_width}:-2"])
    command.extend(
        [
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            str(preview_path),
        ]
    )
    subprocess.run(command, check=True, capture_output=True, text=True)
    return preview_path


def build_event_annotation_template(task: ClipTask, preview_path: str | Path) -> EventAnnotation:
    return EventAnnotation(
        annotation_id=f"ann-{task.task_id}",
        asset_id=task.asset_id,
        camera_id=task.camera_id,
        source_path=task.source_path,
        start_time_s=task.start_time_s,
        end_time_s=task.end_time_s,
        label=AnnotationLabel.UNKNOWN,
        task_id=task.task_id,
        quality_tags=list(task.tags),
        annotator=None,
        notes="",
        metadata={
            "preview_path": str(preview_path),
            "task_priority": task.priority,
            "task_status": task.status,
            **dict(task.metadata),
        },
    )


def build_review_html(preview_records: list[PreviewRecord], output_dir: Path) -> str:
    cards = "\n".join(build_review_card(record, output_dir) for record in preview_records)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>thesis3 Annotation Review Pack</title>
  <style>
    body {{
      font-family: Arial, sans-serif;
      margin: 24px;
      background: #f7f7f7;
      color: #1f2937;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
      gap: 16px;
    }}
    .card {{
      background: white;
      border: 1px solid #d1d5db;
      border-radius: 10px;
      padding: 16px;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
    }}
    video {{
      width: 100%;
      border-radius: 8px;
      background: black;
      margin-bottom: 12px;
    }}
    .meta {{
      font-size: 14px;
      line-height: 1.5;
      white-space: pre-wrap;
    }}
    h1 {{
      margin-bottom: 8px;
    }}
    p {{
      margin-bottom: 20px;
      color: #4b5563;
    }}
  </style>
</head>
<body>
  <h1>thesis3 Annotation Review Pack</h1>
  <p>Use this page to review clip previews, then fill <code>event_annotations.template.jsonl</code> with bird presence labels and notes.</p>
  <div class="grid">
    {cards}
  </div>
</body>
</html>
"""


def build_review_card(record: PreviewRecord, output_dir: Path) -> str:
    preview_relpath = Path(record.preview_path).resolve().relative_to(output_dir.resolve())
    tags = ", ".join(record.tags) if record.tags else "-"
    meta_text = "\n".join(
        [
            f"task_id: {record.task_id}",
            f"camera_id: {record.camera_id}",
            f"asset_id: {record.asset_id}",
            f"source_path: {record.source_path}",
            f"time_range_s: {record.start_time_s:.3f} -> {record.end_time_s:.3f}",
            f"duration_s: {record.duration_s:.3f}",
            f"tags: {tags}",
        ]
    )
    return f"""<section class="card">
  <video controls preload="metadata" src="{escape(preview_relpath.as_posix())}"></video>
  <div class="meta">{escape(meta_text)}</div>
</section>"""
