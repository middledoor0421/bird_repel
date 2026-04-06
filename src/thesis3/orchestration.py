from __future__ import annotations

from abc import ABC, abstractmethod

from thesis3.core import DetectionCandidate, FactoryRegistry, FramePacket, TrackState
from thesis3.dataclass_compat import dataclass, field


@dataclass(slots=True)
class TriggerDecision:
    should_verify: bool
    trigger_reason: str
    metadata: dict = field(default_factory=dict)


class TriggerPolicy(ABC):
    version: str

    @abstractmethod
    def evaluate(
        self,
        candidate: DetectionCandidate,
        track: TrackState,
        source_frame: FramePacket,
        target_frame: FramePacket | None,
    ) -> TriggerDecision:
        raise NotImplementedError


class CandidateSelector(ABC):
    version: str

    @abstractmethod
    def select(
        self,
        candidates: list[DetectionCandidate],
        frame: FramePacket,
        max_candidates: int,
    ) -> list[DetectionCandidate]:
        raise NotImplementedError


class DefaultTriggerPolicy(TriggerPolicy):
    version = "default_trigger_policy_v1"

    def __init__(
        self,
        min_detector_confidence: float = 0.0,
        small_object_area_threshold: float = 1024.0,
        require_target_frame: bool = True,
    ) -> None:
        self.min_detector_confidence = min_detector_confidence
        self.small_object_area_threshold = small_object_area_threshold
        self.require_target_frame = require_target_frame

    def evaluate(
        self,
        candidate: DetectionCandidate,
        track: TrackState,
        source_frame: FramePacket,
        target_frame: FramePacket | None,
    ) -> TriggerDecision:
        if candidate.detector_confidence < self.min_detector_confidence:
            return TriggerDecision(
                should_verify=False,
                trigger_reason="below_trigger_threshold",
                metadata={"candidate_confidence": candidate.detector_confidence},
            )
        if self.require_target_frame and target_frame is None:
            return TriggerDecision(
                should_verify=False,
                trigger_reason="target_frame_unavailable",
                metadata={"source_camera_id": source_frame.camera_id},
            )
        if candidate.bbox is not None and candidate.bbox.area < self.small_object_area_threshold:
            return TriggerDecision(should_verify=True, trigger_reason="small_object_candidate")
        if track.state.value == "confirmed":
            return TriggerDecision(should_verify=True, trigger_reason="confirmed_track")
        return TriggerDecision(should_verify=True, trigger_reason="default_stage2_verification")


class ConfidenceBandTriggerPolicy(TriggerPolicy):
    version = "confidence_band_trigger_policy_v1"

    def __init__(self, low: float = 0.3, high: float = 0.8) -> None:
        self.low = low
        self.high = high

    def evaluate(
        self,
        candidate: DetectionCandidate,
        track: TrackState,
        source_frame: FramePacket,
        target_frame: FramePacket | None,
    ) -> TriggerDecision:
        if target_frame is None:
            return TriggerDecision(False, "target_frame_unavailable")
        score = candidate.detector_confidence
        if score < self.low:
            return TriggerDecision(False, "confidence_too_low")
        if score > self.high:
            return TriggerDecision(False, "confidence_already_high")
        return TriggerDecision(True, "confidence_band_reverification", {"candidate_confidence": score})


class TopKCandidateSelector(CandidateSelector):
    version = "topk_candidate_selector_v1"

    def __init__(self, prefer_small_objects: bool = False) -> None:
        self.prefer_small_objects = prefer_small_objects

    def select(
        self,
        candidates: list[DetectionCandidate],
        frame: FramePacket,
        max_candidates: int,
    ) -> list[DetectionCandidate]:
        if max_candidates <= 0:
            return []

        def ranking_key(candidate: DetectionCandidate):
            area = candidate.bbox.area if candidate.bbox is not None else 0.0
            area_term = -area if self.prefer_small_objects else area
            return (candidate.detector_confidence, area_term)

        ranked = sorted(candidates, key=ranking_key, reverse=True)
        return ranked[:max_candidates]


class ConfidenceBandCandidateSelector(CandidateSelector):
    version = "confidence_band_candidate_selector_v1"

    def __init__(self, min_confidence: float = 0.2, max_confidence: float = 0.8) -> None:
        self.min_confidence = min_confidence
        self.max_confidence = max_confidence

    def select(
        self,
        candidates: list[DetectionCandidate],
        frame: FramePacket,
        max_candidates: int,
    ) -> list[DetectionCandidate]:
        filtered = [
            candidate
            for candidate in candidates
            if self.min_confidence <= candidate.detector_confidence <= self.max_confidence
        ]
        ranked = sorted(filtered, key=lambda candidate: candidate.detector_confidence, reverse=True)
        return ranked[:max_candidates]


def build_orchestration_registries() -> tuple[FactoryRegistry, FactoryRegistry]:
    trigger_registry = FactoryRegistry(expected_base=TriggerPolicy, kind="trigger_policy")
    trigger_registry.register(
        "default_trigger_policy",
        lambda params: DefaultTriggerPolicy(
            min_detector_confidence=float(params.get("min_detector_confidence", 0.0)),
            small_object_area_threshold=float(params.get("small_object_area_threshold", 1024.0)),
            require_target_frame=bool(params.get("require_target_frame", True)),
        ),
    )
    trigger_registry.register(
        "confidence_band_trigger_policy",
        lambda params: ConfidenceBandTriggerPolicy(
            low=float(params.get("low", 0.3)),
            high=float(params.get("high", 0.8)),
        ),
    )

    selector_registry = FactoryRegistry(expected_base=CandidateSelector, kind="candidate_selector")
    selector_registry.register(
        "topk_candidate_selector",
        lambda params: TopKCandidateSelector(
            prefer_small_objects=bool(params.get("prefer_small_objects", False)),
        ),
    )
    selector_registry.register(
        "confidence_band_candidate_selector",
        lambda params: ConfidenceBandCandidateSelector(
            min_confidence=float(params.get("min_confidence", 0.2)),
            max_confidence=float(params.get("max_confidence", 0.8)),
        ),
    )
    return trigger_registry, selector_registry
