from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from thesis3.readiness import format_readiness_report, inspect_pipeline_readiness
from thesis3.stress import PRESET_STRESS_PROFILES
from thesis3.suite_runner import run_experiment_suite


DEFAULT_METHOD_CONFIGS = [
    "configs/scenario_detector_only_baseline.example.json",
    "configs/scenario_bird_sahi_method_bundle.example.json",
    "configs/scenario_ccs_lcs_safety_bundle.example.json",
]


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str | Path, payload: dict[str, Any]) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return output_path


def _resolve_stress_manifests(args: argparse.Namespace) -> list[Path]:
    explicit = [Path(path) for path in (args.stress_manifest or [])]
    if explicit:
        return explicit

    if args.preset:
        return [Path(args.stress_manifest_dir) / f"{preset}.jsonl" for preset in args.preset]

    manifest_dir = Path(args.stress_manifest_dir)
    candidates = sorted(path for path in manifest_dir.glob("*.jsonl") if path.is_file())
    if candidates:
        return candidates
    raise FileNotFoundError(f"No stress manifests found in: {manifest_dir}")


def _rewrite_config_for_stress(
    *,
    base_config_path: str,
    stress_manifest_path: Path,
    output_dir: Path,
) -> Path:
    payload = _load_json(base_config_path)
    base_name = Path(base_config_path).stem
    stress_name = stress_manifest_path.stem
    payload["replay"]["manifest_path"] = str(stress_manifest_path)
    payload["replay"]["output_dir"] = str(output_dir / "runs" / stress_name / base_name)
    payload.setdefault("environment", {})
    payload["environment"]["name"] = f"{payload['environment'].get('name', base_name)}__{stress_name}"
    payload["environment"].setdefault("metadata", {})
    payload["environment"]["metadata"]["stress_profile"] = stress_name
    payload["environment"]["metadata"]["base_config_name"] = base_name
    payload.setdefault("extra", {})
    payload["extra"]["stress_profile"] = stress_name
    payload["extra"]["base_config_name"] = base_name
    payload["extra"]["base_config_path"] = base_config_path
    experiment_group = str(payload["extra"].get("experiment_group", base_name))
    payload["extra"]["experiment_group"] = f"{experiment_group}__stress_{stress_name}"
    config_path = output_dir / "configs" / f"{stress_name}__{base_name}.json"
    return _write_json(config_path, payload)


def _compact_record(record: dict[str, Any]) -> dict[str, Any]:
    summary = record["summary"]
    burden = summary.get("burden", {})
    reasons = summary.get("reason_counters", {})
    run_context = summary.get("run_context", {})
    environment_profile = run_context.get("environment_profile") or {}
    return {
        "config_path": record["config_path"],
        "mode": record["mode"],
        "event_log": record["event_log"],
        "decision_count": record["decision_count"],
        "stress_profile": environment_profile.get("metadata", {}).get("stress_profile"),
        "base_config_name": environment_profile.get("metadata", {}).get("base_config_name"),
        "environment_name": environment_profile.get("name"),
        "actions": summary.get("actions", {}),
        "policy_states": summary.get("policy_states", {}),
        "review_rate": burden.get("review_rate", 0.0),
        "blocked_rate": burden.get("blocked_rate", 0.0),
        "simulated_action_rate": burden.get("simulated_action_rate", 0.0),
        "verification_request_rate_per_decision": burden.get("verification_request_rate_per_decision", 0.0),
        "trigger_reasons": reasons.get("trigger_reasons", {}),
        "verification_schedule_reasons": reasons.get("verification_schedule_reasons", {}),
        "confirmation_reasons": reasons.get("confirmation_reasons", {}),
        "verification_failure_reasons": reasons.get("verification_failure_reasons", {}),
        "safety_policy_reasons": reasons.get("safety_policy_reasons", {}),
    }


def _build_matrix(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(str(record.get("stress_profile") or "unknown"), []).append(record)
    matrix = []
    for stress_profile, rows in sorted(grouped.items()):
        matrix.append(
            {
                "stress_profile": stress_profile,
                "variants": sorted(rows, key=lambda row: str(row.get("base_config_name") or row["config_path"])),
            }
        )
    return matrix


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run baseline, bird-sahi, and safety-policy methods against stressed replay manifests."
    )
    parser.add_argument(
        "--config",
        action="append",
        help="Base config paths to compare. Defaults to baseline + bird-sahi + ccs-lcs example configs.",
    )
    parser.add_argument(
        "--stress-manifest-dir",
        default="artifacts/stress/example_replay",
        help="Directory containing stressed replay manifests.",
    )
    parser.add_argument(
        "--stress-manifest",
        action="append",
        help="Explicit stressed replay manifest path. Repeat to include multiple.",
    )
    parser.add_argument(
        "--preset",
        action="append",
        choices=sorted(PRESET_STRESS_PROFILES),
        help="Resolve stressed manifests from --stress-manifest-dir by preset name.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/suites/method_stress_demo",
        help="Directory for generated configs and suite results.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only generate configs and run readiness checks.",
    )
    parser.add_argument(
        "--allow-not-ready",
        action="store_true",
        help="Run even if readiness checks fail.",
    )
    args = parser.parse_args()

    base_configs = args.config or list(DEFAULT_METHOD_CONFIGS)
    stress_manifests = _resolve_stress_manifests(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    generated_configs = [
        _rewrite_config_for_stress(
            base_config_path=base_config,
            stress_manifest_path=stress_manifest,
            output_dir=output_dir,
        )
        for stress_manifest in stress_manifests
        for base_config in base_configs
    ]

    reports = [inspect_pipeline_readiness(str(path)) for path in generated_configs]
    print("\n\n".join(format_readiness_report(report) for report in reports))
    if any(not report.ready for report in reports) and not args.allow_not_ready:
        return 2
    if args.check_only:
        return 0

    suite_output_path = output_dir / "suite_records.jsonl"
    records = run_experiment_suite(
        config_paths=[str(path) for path in generated_configs],
        output_path=suite_output_path,
    )
    compact_rows = [_compact_record(asdict(record)) for record in records]
    compact_path = output_dir / "compact_summary.json"
    compact_path.write_text(json.dumps(compact_rows, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    matrix_path = output_dir / "matrix.json"
    matrix_path.write_text(json.dumps(_build_matrix(compact_rows), indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(_build_matrix(compact_rows), indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
