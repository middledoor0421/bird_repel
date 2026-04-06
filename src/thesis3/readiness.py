from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from thesis3.components import Detector, Tracker, Verifier, build_default_registries
from thesis3.core import FactoryRegistry, PipelineConfig, PluginSpec, load_pipeline_config
from thesis3.dataclass_compat import asdict, dataclass, field
from thesis3.external_adapters import ExternalAdapterSupport
from thesis3.methodology import build_methodology_registries
from thesis3.orchestration import build_orchestration_registries
from thesis3.plugin_loader import load_symbol
from thesis3.runtime_env import collect_runtime_environment
from thesis3.safety import build_safety_registry


@dataclass(slots=True)
class ReadinessFinding:
    level: str
    scope: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ConfigReadinessReport:
    config_path: str
    scenario: str | None
    runtime_env: dict[str, Any] = field(default_factory=dict)
    findings: list[ReadinessFinding] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for finding in self.findings if finding.level == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for finding in self.findings if finding.level == "warning")

    @property
    def ready(self) -> bool:
        return self.error_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_path": self.config_path,
            "scenario": self.scenario,
            "runtime_env": self.runtime_env,
            "ready": self.ready,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "findings": [asdict(finding) for finding in self.findings],
        }


def _resolve_runtime_path(path_value: str | Path) -> Path:
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate
    return (Path.cwd() / candidate).resolve()


def _add_finding(
    report: ConfigReadinessReport,
    level: str,
    scope: str,
    message: str,
    **details: Any,
) -> None:
    report.findings.append(ReadinessFinding(level=level, scope=scope, message=message, details=details))


def _check_file_path(
    report: ConfigReadinessReport,
    *,
    scope: str,
    label: str,
    raw_path: str | None,
    required: bool = True,
) -> None:
    if raw_path is None or raw_path == "":
        if required:
            _add_finding(report, "error", scope, f"{label} is missing.")
        return
    resolved = _resolve_runtime_path(raw_path)
    if resolved.exists():
        _add_finding(report, "info", scope, f"{label} exists.", raw_path=raw_path, resolved_path=str(resolved))
    else:
        _add_finding(report, "error", scope, f"{label} does not exist.", raw_path=raw_path, resolved_path=str(resolved))


def _check_model_target_path(
    report: ConfigReadinessReport,
    *,
    scope: str,
    model_target: str | None,
) -> None:
    if not model_target:
        return
    module_ref, _, symbol_name = model_target.rpartition(":")
    if not module_ref or not symbol_name:
        _add_finding(report, "error", scope, "model_target must use '<module_or_path>:<symbol>' format.", model_target=model_target)
        return

    if module_ref.endswith(".py") or module_ref.startswith("/") or module_ref.startswith("./") or module_ref.startswith("../"):
        _check_file_path(report, scope=scope, label="model_target file", raw_path=module_ref)
    try:
        load_symbol(model_target)
    except Exception as exc:  # noqa: BLE001
        _add_finding(
            report,
            "error",
            scope,
            "Unable to load model_target symbol.",
            model_target=model_target,
            error_type=type(exc).__name__,
            error=str(exc),
        )
    else:
        _add_finding(report, "info", scope, "model_target symbol loaded.", model_target=model_target)


def _check_common_plugin_paths(
    report: ConfigReadinessReport,
    *,
    role: str,
    spec: PluginSpec,
) -> None:
    params = spec.params
    scope = f"{role}.params"
    model_target = params.get("model_target")
    if isinstance(model_target, str):
        _check_model_target_path(report, scope=scope, model_target=model_target)

    class_mapping_path = params.get("class_mapping_path")
    if isinstance(class_mapping_path, str):
        _check_file_path(report, scope=scope, label="class_mapping_path", raw_path=class_mapping_path)

    for entry in params.get("sys_path_entries", []):
        if isinstance(entry, str):
            _check_file_path(report, scope=scope, label="sys_path_entry", raw_path=entry)

    model_init_params = params.get("model_init_params")
    if not isinstance(model_init_params, dict):
        return
    for key in ("weights", "weight", "checkpoint", "ckpt", "model_path"):
        value = model_init_params.get(key)
        if isinstance(value, str):
            _check_file_path(report, scope=scope, label=key, raw_path=value)


def _check_registry_plugin(
    report: ConfigReadinessReport,
    *,
    role: str,
    spec: PluginSpec | None,
    registry: FactoryRegistry,
    instantiate_plugins: bool,
    instantiate_external_targets: bool,
) -> None:
    if spec is None:
        _add_finding(report, "info", role, "Plugin is not configured for this role.")
        return

    if spec.name in registry.names():
        _add_finding(report, "info", role, "Registered plugin found.", plugin_name=spec.name)
    elif ":" in spec.name:
        try:
            load_symbol(spec.name)
        except Exception as exc:  # noqa: BLE001
            _add_finding(
                report,
                "error",
                role,
                "Dynamic plugin target failed to load.",
                plugin_name=spec.name,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            return
        else:
            _add_finding(report, "info", role, "Dynamic plugin target loaded.", plugin_name=spec.name)
    else:
        _add_finding(report, "error", role, "Unknown plugin name.", plugin_name=spec.name)
        return

    _check_common_plugin_paths(report, role=role, spec=spec)

    if instantiate_plugins:
        try:
            instance = registry.create(spec)
        except Exception as exc:  # noqa: BLE001
            _add_finding(
                report,
                "error",
                role,
                "Plugin failed to instantiate.",
                plugin_name=spec.name,
                error_type=type(exc).__name__,
                error=str(exc),
            )
        else:
            _add_finding(
                report,
                "info",
                role,
                "Plugin instantiated.",
                plugin_name=spec.name,
                instance_type=type(instance).__name__,
                version=getattr(instance, "version", None),
            )

    if not instantiate_external_targets:
        return

    params = spec.params
    model_target = params.get("model_target")
    if not isinstance(model_target, str):
        return
    model_init_params = params.get("model_init_params")
    if model_init_params is not None and not isinstance(model_init_params, dict):
        _add_finding(report, "error", role, "model_init_params must be a mapping.", plugin_name=spec.name)
        return

    try:
        external_instance = ExternalAdapterSupport().instantiate_external_symbol(
            model_target,
            init_params=model_init_params,
            sys_path_entries=params.get("sys_path_entries"),
        )
    except Exception as exc:  # noqa: BLE001
        _add_finding(
            report,
            "error",
            role,
            "External model target failed to instantiate.",
            plugin_name=spec.name,
            model_target=model_target,
            error_type=type(exc).__name__,
            error=str(exc),
        )
    else:
        _add_finding(
            report,
            "info",
            role,
            "External model target instantiated.",
            plugin_name=spec.name,
            model_target=model_target,
            instance_type=type(external_instance).__name__,
        )


def inspect_pipeline_readiness(
    config_path: str | Path,
    *,
    instantiate_plugins: bool = True,
    instantiate_external_targets: bool = True,
) -> ConfigReadinessReport:
    resolved_config = _resolve_runtime_path(config_path)
    report = ConfigReadinessReport(
        config_path=str(resolved_config),
        scenario=None,
        runtime_env=collect_runtime_environment(),
    )
    if not resolved_config.exists():
        _add_finding(report, "error", "config", "Config file does not exist.", resolved_path=str(resolved_config))
        return report

    try:
        config = load_pipeline_config(resolved_config)
    except Exception as exc:  # noqa: BLE001
        _add_finding(
            report,
            "error",
            "config",
            "Config failed to load.",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return report

    report.scenario = config.scenario
    _add_finding(report, "info", "config", "Config loaded.", scenario=config.scenario, config_path=str(resolved_config))
    _check_pipeline_paths(report, config)
    _check_pipeline_plugins(
        report,
        config,
        instantiate_plugins=instantiate_plugins,
        instantiate_external_targets=instantiate_external_targets,
    )
    return report


def _check_pipeline_paths(report: ConfigReadinessReport, config: PipelineConfig) -> None:
    _check_file_path(
        report,
        scope="replay",
        label="manifest_path",
        raw_path=config.replay.manifest_path,
    )
    output_dir = _resolve_runtime_path(config.replay.output_dir)
    if output_dir.exists():
        _add_finding(report, "info", "replay", "output_dir already exists.", output_dir=str(output_dir))
    else:
        _add_finding(report, "warning", "replay", "output_dir does not exist yet and will be created on run.", output_dir=str(output_dir))


def _check_pipeline_plugins(
    report: ConfigReadinessReport,
    config: PipelineConfig,
    *,
    instantiate_plugins: bool,
    instantiate_external_targets: bool,
) -> None:
    detector_registry, verifier_registry, tracker_registry = build_default_registries()
    trigger_registry, selector_registry = build_orchestration_registries()
    scheduler_registry, confirmation_registry = build_methodology_registries()
    safety_registry = build_safety_registry()

    plugin_specs: list[tuple[str, PluginSpec | None, FactoryRegistry]] = [
        ("detector", config.detector, detector_registry),
        ("verifier", config.verifier, verifier_registry),
        ("tracker", config.tracker or PluginSpec(name="simple_tracker"), tracker_registry),
        ("trigger_policy", config.trigger_policy or PluginSpec(name="default_trigger_policy"), trigger_registry),
        ("candidate_selector", config.candidate_selector or PluginSpec(name="topk_candidate_selector"), selector_registry),
        (
            "verification_scheduler",
            config.verification_scheduler or PluginSpec(name="default_verification_scheduler"),
            scheduler_registry,
        ),
        (
            "confirmation_policy",
            config.confirmation_policy or PluginSpec(name="noop_confirmation_policy"),
            confirmation_registry,
        ),
        ("safety_policy", config.safety_policy or PluginSpec(name="noop_safety_policy"), safety_registry),
    ]

    for role, spec, registry in plugin_specs:
        _check_registry_plugin(
            report,
            role=role,
            spec=spec,
            registry=registry,
            instantiate_plugins=instantiate_plugins,
            instantiate_external_targets=instantiate_external_targets,
        )


def format_readiness_report(report: ConfigReadinessReport) -> str:
    header = [
        f"config={report.config_path}",
        f"scenario={report.scenario or 'unknown'}",
        f"conda_env={report.runtime_env.get('conda_default_env') or 'none'}",
        f"python={report.runtime_env.get('python_executable')}",
        f"ready={'yes' if report.ready else 'no'}",
        f"errors={report.error_count}",
        f"warnings={report.warning_count}",
    ]
    lines = [" ".join(header)]
    for finding in report.findings:
        suffix = ""
        if finding.details:
            suffix = f" | {json.dumps(finding.details, ensure_ascii=True, sort_keys=True)}"
        lines.append(f"[{finding.level.upper()}] {finding.scope}: {finding.message}{suffix}")
    return "\n".join(lines)
