from __future__ import annotations

import argparse
from dataclasses import asdict
from itertools import product
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from thesis3.readiness import format_readiness_report, inspect_pipeline_readiness
from thesis3.suite_runner import run_experiment_suite


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _dump_json(path: str | Path, payload: dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _set_nested(mapping: dict[str, Any], dotted_path: str, value: Any) -> None:
    current = mapping
    segments = dotted_path.split(".")
    for segment in segments[:-1]:
        next_value = current.get(segment)
        if not isinstance(next_value, dict):
            next_value = {}
            current[segment] = next_value
        current = next_value
    current[segments[-1]] = value


def _variant_name(
    *,
    confirm_len: int,
    min_verifier_score: float,
    verifier_score_threshold: float,
    interval: int,
    bootstrap_first_n: int,
    use_track_local_index: bool,
) -> str:
    return (
        f"confirm_len-{confirm_len}"
        f"__confirm_score-{min_verifier_score:.2f}"
        f"__verifier_score-{verifier_score_threshold:.2f}"
        f"__interval-{interval}"
        f"__bootstrap-{bootstrap_first_n}"
        f"__track_local-{int(use_track_local_index)}"
    )


def _objective(summary: dict[str, Any]) -> float:
    burden = summary.get("burden", {})
    return (
        float(burden.get("simulated_action_rate", 0.0))
        - float(burden.get("review_rate", 0.0))
        - (0.25 * float(burden.get("blocked_rate", 0.0)))
        - (0.10 * float(burden.get("verification_request_rate_per_decision", 0.0)))
    )


def _summarize_record(record: dict[str, Any], *, variant_name: str | None = None) -> dict[str, Any]:
    summary = record["summary"]
    burden = summary.get("burden", {})
    reasons = summary.get("reason_counters", {})
    return {
        "variant_name": variant_name or Path(record["config_path"]).stem,
        "config_path": record["config_path"],
        "event_log": record["event_log"],
        "objective": _objective(summary),
        "review_rate": burden.get("review_rate", 0.0),
        "simulated_action_rate": burden.get("simulated_action_rate", 0.0),
        "blocked_rate": burden.get("blocked_rate", 0.0),
        "verification_request_rate_per_decision": burden.get("verification_request_rate_per_decision", 0.0),
        "actions": summary.get("actions", {}),
        "policy_states": summary.get("policy_states", {}),
        "verification_schedule_reasons": reasons.get("verification_schedule_reasons", {}),
        "confirmation_reasons": reasons.get("confirmation_reasons", {}),
        "verification_failure_reasons": reasons.get("verification_failure_reasons", {}),
        "verification_outcomes": reasons.get("verification_outcomes", {}),
        "runtime_env": summary.get("run_context", {}).get("runtime_env", {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sweep bird-sahi confirmation operating points against a fixed baseline."
    )
    parser.add_argument(
        "--baseline-config",
        default="configs/scenario_detector_only_baseline.example.json",
        help="Detector-only baseline config.",
    )
    parser.add_argument(
        "--confirm-config",
        default="configs/scenario_bird_sahi_method_bundle.local.json",
        help="Base confirm config to clone and tune.",
    )
    parser.add_argument(
        "--noconfirm-config",
        default="configs/scenario_bird_sahi_noconfirm.local.json",
        help="Optional no-confirm reference config.",
    )
    parser.add_argument("--confirm-len", action="append", type=int, help="Repeat to sweep confirmation length.")
    parser.add_argument(
        "--min-verifier-score",
        action="append",
        type=float,
        help="Repeat to sweep confirmation min_verifier_score.",
    )
    parser.add_argument(
        "--verifier-score-threshold",
        action="append",
        type=float,
        help="Repeat to sweep verifier score_threshold.",
    )
    parser.add_argument("--interval", action="append", type=int, help="Repeat to sweep scheduler interval.")
    parser.add_argument(
        "--bootstrap-first-n",
        action="append",
        type=int,
        help="Repeat to sweep scheduler bootstrap_first_n.",
    )
    parser.add_argument(
        "--use-track-local-index",
        action="append",
        choices=["true", "false"],
        help="Repeat to sweep whether keyframe scheduling uses track-local index.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/sweeps/bird_sahi_operating_point",
        help="Directory to store generated configs and suite outputs.",
    )
    parser.add_argument(
        "--include-noconfirm",
        action="store_true",
        help="Include the no-confirm config as a reference run.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only generate configs and readiness reports without running them.",
    )
    parser.add_argument(
        "--allow-not-ready",
        action="store_true",
        help="Run even if one of the generated configs fails readiness.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    generated_config_dir = output_dir / "configs"
    generated_config_dir.mkdir(parents=True, exist_ok=True)

    base_confirm_config = _load_json(args.confirm_config)
    confirm_params = base_confirm_config["confirmation_policy"]["params"]
    verifier_params = base_confirm_config["verifier"]["params"]
    scheduler_params = base_confirm_config["verification_scheduler"]["params"]

    confirm_lens = args.confirm_len or [int(confirm_params.get("confirm_len", 2))]
    min_verifier_scores = args.min_verifier_score or [float(confirm_params.get("min_verifier_score", 0.0))]
    verifier_score_thresholds = args.verifier_score_threshold or [float(verifier_params.get("score_threshold", 0.0))]
    intervals = args.interval or [int(scheduler_params.get("interval", 4))]
    bootstrap_first_ns = args.bootstrap_first_n or [int(scheduler_params.get("bootstrap_first_n", 0))]
    use_track_local_flags = (
        [value.lower() == "true" for value in args.use_track_local_index]
        if args.use_track_local_index
        else [bool(scheduler_params.get("use_track_local_index", False))]
    )

    generated_configs: list[tuple[str, str]] = []
    for confirm_len, min_verifier_score, verifier_score_threshold, interval, bootstrap_first_n, use_track_local_index in product(
        confirm_lens,
        min_verifier_scores,
        verifier_score_thresholds,
        intervals,
        bootstrap_first_ns,
        use_track_local_flags,
    ):
        payload = json.loads(json.dumps(base_confirm_config))
        variant_name = _variant_name(
            confirm_len=confirm_len,
            min_verifier_score=min_verifier_score,
            verifier_score_threshold=verifier_score_threshold,
            interval=interval,
            bootstrap_first_n=bootstrap_first_n,
            use_track_local_index=use_track_local_index,
        )
        payload["replay"]["output_dir"] = str(output_dir / "runs" / variant_name)
        payload.setdefault("extra", {})
        payload["extra"]["experiment_group"] = "bird_sahi_confirm_sweep"
        payload["extra"]["sweep_variant_name"] = variant_name
        payload["extra"]["sweep_parameters"] = {
            "confirm_len": confirm_len,
            "min_verifier_score": min_verifier_score,
            "verifier_score_threshold": verifier_score_threshold,
            "interval": interval,
            "bootstrap_first_n": bootstrap_first_n,
            "use_track_local_index": use_track_local_index,
        }
        payload["environment"]["name"] = f"{payload['environment']['name']}__{variant_name}"
        payload["environment"].setdefault("metadata", {})
        payload["environment"]["metadata"]["sweep_variant_name"] = variant_name

        _set_nested(payload, "confirmation_policy.params.confirm_len", confirm_len)
        _set_nested(payload, "confirmation_policy.params.min_verifier_score", min_verifier_score)
        _set_nested(payload, "verifier.params.score_threshold", verifier_score_threshold)
        _set_nested(payload, "verification_scheduler.params.interval", interval)
        _set_nested(payload, "verification_scheduler.params.bootstrap_first_n", bootstrap_first_n)
        _set_nested(payload, "verification_scheduler.params.use_track_local_index", use_track_local_index)

        config_path = generated_config_dir / f"{variant_name}.json"
        _dump_json(config_path, payload)
        generated_configs.append((variant_name, str(config_path)))

    ordered_config_paths = [args.baseline_config]
    if args.include_noconfirm:
        ordered_config_paths.append(args.noconfirm_config)
    ordered_config_paths.extend(config_path for _, config_path in generated_configs)

    reports = [inspect_pipeline_readiness(config_path) for config_path in ordered_config_paths]
    print("\n\n".join(format_readiness_report(report) for report in reports))
    if any(not report.ready for report in reports) and not args.allow_not_ready:
        return 2
    if args.check_only:
        return 0

    suite_output_path = output_dir / "suite_records.jsonl"
    records = run_experiment_suite(config_paths=ordered_config_paths, output_path=suite_output_path)
    variant_name_by_config = {config_path: variant_name for variant_name, config_path in generated_configs}
    compact_rows = []
    for record in records:
        row = _summarize_record(
            asdict(record),
            variant_name=variant_name_by_config.get(record.config_path),
        )
        compact_rows.append(row)

    ranked_rows = sorted(
        compact_rows,
        key=lambda row: (
            -float(row["objective"]),
            float(row["review_rate"]),
            -float(row["simulated_action_rate"]),
        ),
    )
    ranking_path = output_dir / "ranking.json"
    ranking_path.write_text(json.dumps(ranked_rows, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(ranked_rows, indent=2, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
