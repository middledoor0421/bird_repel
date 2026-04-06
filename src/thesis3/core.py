from __future__ import annotations

from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from thesis3.dataclass_compat import asdict, dataclass, field, is_dataclass


class SyncStatus(str, Enum):
    SYNCED = "synced"
    UNSYNCED = "unsynced"
    ESTIMATED = "estimated"


class TrackLifecycleState(str, Enum):
    NEW = "new"
    TENTATIVE = "tentative"
    CONFIRMED = "confirmed"
    LOST = "lost"


class ActionState(str, Enum):
    NO_ACTION = "NO_ACTION"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    SIMULATED_ACTION = "SIMULATED_ACTION"
    BLOCKED_BY_SAFETY_GATE = "BLOCKED_BY_SAFETY_GATE"


@dataclass(slots=True)
class BBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def area(self) -> float:
        return max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)


@dataclass(slots=True)
class FramePacket:
    frame_id: str
    camera_id: str
    timestamp: float
    image_ref: str
    metadata: dict[str, Any] = field(default_factory=dict)
    sync_status: SyncStatus = SyncStatus.SYNCED


@dataclass(slots=True)
class DetectionCandidate:
    candidate_id: str
    frame_id: str
    camera_id: str
    bbox: BBox | None
    class_name: str
    detector_confidence: float
    detector_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DetectorResult:
    candidates: list[DetectionCandidate]
    latency_ms: float
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TrackState:
    track_id: str
    candidate_ids: list[str]
    start_time: float
    last_seen_time: float
    camera_history: list[str]
    state: TrackLifecycleState
    track_confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TrackerUpdate:
    tracks: list[TrackState]
    association: dict[str, str]
    lost_tracks: list[str]
    new_tracks: list[str]
    latency_ms: float = 0.0


@dataclass(slots=True)
class VerificationRequest:
    request_id: str
    source_track_id: str
    source_camera_id: str
    target_camera_id: str
    roi_hint: BBox | None
    trigger_reason: str
    deadline_ms: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class VerificationResult:
    request_id: str
    verified: bool
    verifier_score: float
    verifier_version: str
    latency_ms: float = 0.0
    supporting_bbox: BBox | None = None
    quality_score: float | None = None
    failure_reason: str | None = None
    uncertainty: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LatencyBreakdown:
    detector_latency_ms: float
    tracker_latency_ms: float
    verification_latency_ms: float | None = None
    policy_latency_ms: float | None = None
    actuator_latency_ms: float | None = None
    end_to_end_compute_latency_ms: float | None = None
    source_to_decision_latency_ms: float | None = None


@dataclass(slots=True)
class DecisionRecord:
    track_id: str
    stage1_summary: dict[str, Any]
    stage2_summary: dict[str, Any] | None
    policy_state: str
    action_state: ActionState
    human_review_required: bool
    timestamp: float
    latency: LatencyBreakdown | None = None
    reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PluginSpec:
    name: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CameraSpec:
    camera_id: str
    role: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EnvironmentProfile:
    name: str = "default"
    target_labels: list[str] = field(default_factory=lambda: ["target"])
    non_target_labels: list[str] = field(default_factory=list)
    safe_zone: dict[str, Any] = field(default_factory=dict)
    latency_budget_ms: float | None = None
    review_budget_per_minute: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ReplayConfig:
    manifest_path: str
    timestamp_tolerance_ms: int = 0
    output_dir: str = "artifacts/default"


@dataclass(slots=True)
class PolicyConfig:
    verification_threshold: float = 0.7
    review_threshold: float = 0.5
    quality_threshold: float = 0.3
    max_candidates_per_tick: int = 3


@dataclass(slots=True)
class SimulationConfig:
    actuator_enabled: bool = True
    actuator_failure_rate: float = 0.0


@dataclass(slots=True)
class PipelineConfig:
    scenario: str
    cameras: list[CameraSpec]
    replay: ReplayConfig
    detector: PluginSpec
    verifier: PluginSpec | None = None
    tracker: PluginSpec | None = None
    trigger_policy: PluginSpec | None = None
    candidate_selector: PluginSpec | None = None
    verification_scheduler: PluginSpec | None = None
    confirmation_policy: PluginSpec | None = None
    safety_policy: PluginSpec | None = None
    environment: EnvironmentProfile = field(default_factory=EnvironmentProfile)
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    simulator: SimulationConfig = field(default_factory=SimulationConfig)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PipelineConfig":
        replay = ReplayConfig(**payload["replay"])
        cameras = [CameraSpec(**camera) for camera in payload["cameras"]]
        detector = PluginSpec(**payload["detector"])
        verifier = PluginSpec(**payload["verifier"]) if payload.get("verifier") else None
        tracker = PluginSpec(**payload["tracker"]) if payload.get("tracker") else None
        trigger_policy = PluginSpec(**payload["trigger_policy"]) if payload.get("trigger_policy") else None
        candidate_selector = PluginSpec(**payload["candidate_selector"]) if payload.get("candidate_selector") else None
        verification_scheduler = (
            PluginSpec(**payload["verification_scheduler"]) if payload.get("verification_scheduler") else None
        )
        confirmation_policy = (
            PluginSpec(**payload["confirmation_policy"]) if payload.get("confirmation_policy") else None
        )
        safety_policy = PluginSpec(**payload["safety_policy"]) if payload.get("safety_policy") else None
        environment = EnvironmentProfile(**payload.get("environment", {}))
        policy = PolicyConfig(**payload.get("policy", {}))
        simulator = SimulationConfig(**payload.get("simulator", {}))
        return cls(
            scenario=payload["scenario"],
            cameras=cameras,
            replay=replay,
            detector=detector,
            verifier=verifier,
            tracker=tracker,
            trigger_policy=trigger_policy,
            candidate_selector=candidate_selector,
            verification_scheduler=verification_scheduler,
            confirmation_policy=confirmation_policy,
            safety_policy=safety_policy,
            environment=environment,
            policy=policy,
            simulator=simulator,
            extra=payload.get("extra", {}),
        )


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "YAML config requires PyYAML. Use JSON or install PyYAML before loading YAML configs."
        ) from exc
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return loaded


def load_pipeline_config(path: str | Path) -> PipelineConfig:
    config_path = Path(path)
    if config_path.suffix.lower() == ".json":
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    elif config_path.suffix.lower() in {".yaml", ".yml"}:
        payload = _load_yaml(config_path)
    else:
        raise ValueError(f"Unsupported config format: {config_path.suffix}")
    return PipelineConfig.from_dict(payload)


def to_serializable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return {key: to_serializable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): to_serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_serializable(item) for item in value]
    return value


def stable_hash(value: Any) -> str:
    normalized = json.dumps(to_serializable(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


class FactoryRegistry:
    def __init__(self, expected_base: type | None = None, kind: str = "plugin") -> None:
        self._factories: dict[str, Callable[[dict[str, Any]], Any]] = {}
        self._expected_base = expected_base
        self._kind = kind

    def register(self, name: str, factory: Callable[[dict[str, Any]], Any]) -> None:
        if name in self._factories:
            raise ValueError(f"Factory already registered: {name}")
        self._factories[name] = factory

    def create(self, spec: PluginSpec | None) -> Any:
        from thesis3.plugin_loader import instantiate_dynamic_plugin

        if spec is None:
            raise ValueError("Plugin spec is required.")
        if spec.name in self._factories:
            instance = self._factories[spec.name](spec.params)
        elif ":" in spec.name:
            instance = instantiate_dynamic_plugin(spec.name, spec.params)
        else:
            raise KeyError(f"Unknown {self._kind}: {spec.name}")

        if self._expected_base is not None and not isinstance(instance, self._expected_base):
            raise TypeError(
                f"{self._kind} '{spec.name}' must implement {self._expected_base.__name__}, "
                f"got {type(instance).__name__}"
            )
        return instance

    def names(self) -> list[str]:
        return sorted(self._factories)
