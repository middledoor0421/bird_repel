from __future__ import annotations

from pathlib import Path
from time import perf_counter, sleep
from uuid import uuid4

from thesis3.components import build_default_registries
from thesis3.methodology import build_methodology_registries
from thesis3.orchestration import build_orchestration_registries
from thesis3.core import PipelineConfig, PluginSpec, load_pipeline_config, stable_hash
from thesis3.events import JsonlEventStore
from thesis3.pipelines import PipelineContext, build_pipeline
from thesis3.policy import PolicyGate
from thesis3.replay import ReplayManifestReader, group_packets_by_timestamp
from thesis3.runtime_env import collect_runtime_environment
from thesis3.safety import build_safety_registry
from thesis3.simulation import ActuatorSimulator


def build_runtime(config_path: str | Path) -> PipelineContext:
    config = load_pipeline_config(config_path)
    run_id = f"{config.scenario}-{uuid4().hex[:8]}"
    detector_registry, verifier_registry, tracker_registry = build_default_registries()
    trigger_registry, selector_registry = build_orchestration_registries()
    scheduler_registry, confirmation_registry = build_methodology_registries()
    safety_registry = build_safety_registry()

    detector = detector_registry.create(config.detector)
    verifier = verifier_registry.create(config.verifier) if config.verifier is not None else None
    tracker = tracker_registry.create(config.tracker or PluginSpec(name="simple_tracker"))
    trigger_policy = trigger_registry.create(config.trigger_policy or PluginSpec(name="default_trigger_policy"))
    candidate_selector = selector_registry.create(
        config.candidate_selector or PluginSpec(name="topk_candidate_selector")
    )
    verification_scheduler = scheduler_registry.create(
        config.verification_scheduler or PluginSpec(name="default_verification_scheduler")
    )
    confirmation_policy = confirmation_registry.create(
        config.confirmation_policy or PluginSpec(name="noop_confirmation_policy")
    )
    safety_policy = safety_registry.create(config.safety_policy or PluginSpec(name="noop_safety_policy"))
    event_store = JsonlEventStore(Path(config.replay.output_dir) / f"{run_id}.jsonl")
    policy_gate = PolicyGate(config.policy)
    actuator = ActuatorSimulator(
        enabled=config.simulator.actuator_enabled,
        failure_rate=config.simulator.actuator_failure_rate,
    )

    runtime = PipelineContext(
        config=config,
        run_id=run_id,
        detector=detector,
        verifier=verifier,
        tracker=tracker,
        trigger_policy=trigger_policy,
        candidate_selector=candidate_selector,
        verification_scheduler=verification_scheduler,
        confirmation_policy=confirmation_policy,
        safety_policy=safety_policy,
        policy_gate=policy_gate,
        actuator=actuator,
        event_store=event_store,
    )
    runtime.log(
        "run_start",
        {
            "run_id": run_id,
            "scenario": config.scenario,
            "config_hash": stable_hash(config),
            "manifest_path": config.replay.manifest_path,
            "environment_profile": config.environment,
            "runtime_env": collect_runtime_environment(),
            "method_hooks": {
                "trigger_policy": config.trigger_policy.name if config.trigger_policy is not None else "default_trigger_policy",
                "candidate_selector": (
                    config.candidate_selector.name if config.candidate_selector is not None else "topk_candidate_selector"
                ),
                "verification_scheduler": (
                    config.verification_scheduler.name
                    if config.verification_scheduler is not None
                    else "default_verification_scheduler"
                ),
                "confirmation_policy": (
                    config.confirmation_policy.name
                    if config.confirmation_policy is not None
                    else "noop_confirmation_policy"
                ),
                "safety_policy": (
                    config.safety_policy.name
                    if config.safety_policy is not None
                    else "noop_safety_policy"
                ),
            },
        },
    )
    return runtime


def execute_replay(config_path: str | Path, emulate_realtime: bool = False) -> tuple[str, list[dict]]:
    started_at = perf_counter()
    runtime = build_runtime(config_path)
    reader = ReplayManifestReader(runtime.config.replay.manifest_path)
    packets = reader.read_packets()
    groups = group_packets_by_timestamp(packets, runtime.config.replay.timestamp_tolerance_ms)
    pipeline = build_pipeline(runtime)

    decisions = []
    previous_timestamp: float | None = None

    for group in groups:
        anchor = group[0].timestamp
        if emulate_realtime and previous_timestamp is not None:
            delay_seconds = max(0.0, anchor - previous_timestamp)
            sleep(min(delay_seconds, 0.25))
        decisions.extend(pipeline.process_group(group))
        previous_timestamp = anchor

    replay_span_ms = 0.0
    if packets:
        replay_span_ms = max(0.0, (packets[-1].timestamp - packets[0].timestamp) * 1000.0)
    runtime.log(
        "run_complete",
        {
            "run_id": runtime.run_id,
            "decision_count": len(decisions),
            "group_count": len(groups),
            "replay_span_ms": replay_span_ms,
            "wall_clock_elapsed_ms": (perf_counter() - started_at) * 1000.0,
        },
    )
    return str(runtime.event_store.path), [decision.stage1_summary for decision in decisions]
