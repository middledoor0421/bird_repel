from __future__ import annotations

from typing import Any


def render_gt_eval_report(summary: dict[str, Any]) -> str:
    lines: list[str] = ["# GT Evaluation Report", ""]

    metadata = summary.get("metadata") or {}
    if metadata:
        lines.append("## Suite Setup")
        for key, value in metadata.items():
            lines.append(f"- `{key}`: `{value}`")
        lines.append("")

    matrix = summary.get("matrix") or []
    if matrix:
        lines.append("## Matrix")
        lines.extend(_render_table(matrix))
        lines.append("")

    records = summary.get("records") or []
    if records:
        lines.append("## Records")
        for record in records:
            label = record.get("label", "unnamed")
            lines.append(f"### {label}")
            lines.append(f"- `event_log_path`: `{record.get('event_log_path')}`")
            event_summary = record.get("event_summary")
            if event_summary:
                lines.append(
                    "- event:"
                    f" positive_hit={event_summary.get('positive_hit_count')}"
                    f", positive_miss={event_summary.get('positive_miss_count')}"
                    f", negative_false_alert={event_summary.get('negative_false_alert_count')}"
                    f", unmatched_alert={event_summary.get('unmatched_alert_decision_count')}"
                )
            frame_summary = record.get("frame_summary")
            if frame_summary:
                lines.append(
                    "- frame:"
                    f" tp={frame_summary.get('true_positive_count')}"
                    f", fn={frame_summary.get('false_negative_count')}"
                    f", fp={frame_summary.get('false_positive_count')}"
                    f", precision={_fmt(frame_summary.get('precision'))}"
                    f", recall={_fmt(frame_summary.get('recall'))}"
                )
            tracking_summary = record.get("tracking_summary")
            if tracking_summary:
                lines.append(
                    "- tracking:"
                    f" continuity_recall={_fmt(tracking_summary.get('continuity_recall'))}"
                    f", id_switch={tracking_summary.get('id_switch_count')}"
                    f", handoff_success_rate={_fmt(tracking_summary.get('handoff_success_rate'))}"
                )
            verification_summary = record.get("verification_summary")
            if verification_summary:
                lines.append(
                    "- verification:"
                    f" true_accept={verification_summary.get('true_accept_count')}"
                    f", false_accept={verification_summary.get('false_accept_count')}"
                    f", false_reject={verification_summary.get('false_reject_count')}"
                    f", true_reject={verification_summary.get('true_reject_count')}"
                )
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _render_table(rows: list[dict[str, Any]]) -> list[str]:
    keys: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in keys:
                keys.append(key)
    header = "| " + " | ".join(keys) + " |"
    divider = "| " + " | ".join(["---"] * len(keys)) + " |"
    body = []
    for row in rows:
        values = [_fmt(row.get(key)) for key in keys]
        body.append("| " + " | ".join(values) + " |")
    return [header, divider, *body]


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    if value is None:
        return ""
    return str(value)
