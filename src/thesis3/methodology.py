from __future__ import annotations

from abc import ABC, abstractmethod
import re
from typing import Any

from thesis3.core import (
    DetectionCandidate,
    EnvironmentProfile,
    FactoryRegistry,
    FramePacket,
    TrackState,
    VerificationResult,
)
from thesis3.dataclass_compat import dataclass, field
from thesis3.image_io import bbox_iou
from thesis3.orchestration import TriggerDecision


@dataclass(slots=True)
class VerificationScheduleDecision:
    should_verify: bool
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


class VerificationScheduler(ABC):
    version: str

    @abstractmethod
    def evaluate(
        self,
        candidate: DetectionCandidate,
        track: TrackState,
        source_frame: FramePacket,
        target_frame: FramePacket | None,
        trigger_decision: TriggerDecision,
        selected_for_verification: bool,
        environment: EnvironmentProfile,
    ) -> VerificationScheduleDecision:
        raise NotImplementedError


@dataclass(slots=True)
class ConfirmationDecision:
    confirmed: bool
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ConfirmationPolicy(ABC):
    version: str

    @abstractmethod
    def evaluate(
        self,
        candidate: DetectionCandidate,
        track: TrackState,
        verification: VerificationResult,
        source_frame: FramePacket,
        target_frame: FramePacket | None,
        environment: EnvironmentProfile,
    ) -> ConfirmationDecision:
        raise NotImplementedError


def _resolve_frame_index(frame: FramePacket) -> int | None:
    for key in ("frame_index", "source_index", "sequence_index", "tick_index"):
        raw = frame.metadata.get(key)
        if isinstance(raw, int):
            return raw
        if isinstance(raw, float):
            return int(raw)
        if isinstance(raw, str) and raw.isdigit():
            return int(raw)
    match = re.search(r"(\d+)(?!.*\d)", frame.frame_id)
    if match:
        return int(match.group(1))
    return None


class DefaultVerificationScheduler(VerificationScheduler):
    version = "default_verification_scheduler_v1"

    def __init__(
        self,
        require_trigger: bool = True,
        require_selection: bool = True,
        require_target_frame: bool = True,
    ) -> None:
        self.require_trigger = require_trigger
        self.require_selection = require_selection
        self.require_target_frame = require_target_frame

    def evaluate(
        self,
        candidate: DetectionCandidate,
        track: TrackState,
        source_frame: FramePacket,
        target_frame: FramePacket | None,
        trigger_decision: TriggerDecision,
        selected_for_verification: bool,
        environment: EnvironmentProfile,
    ) -> VerificationScheduleDecision:
        if self.require_selection and not selected_for_verification:
            return VerificationScheduleDecision(
                should_verify=False,
                reason="not_selected_for_verification",
                metadata={"candidate_id": candidate.candidate_id},
            )
        if self.require_trigger and not trigger_decision.should_verify:
            return VerificationScheduleDecision(
                should_verify=False,
                reason=trigger_decision.trigger_reason,
                metadata=dict(trigger_decision.metadata),
            )
        if self.require_target_frame and target_frame is None:
            return VerificationScheduleDecision(
                should_verify=False,
                reason="target_frame_unavailable",
                metadata={"source_camera_id": source_frame.camera_id},
            )
        return VerificationScheduleDecision(
            should_verify=True,
            reason="scheduled_by_default_policy",
            metadata={
                "environment": environment.name,
                "selected_for_verification": selected_for_verification,
            },
        )


class PeriodicVerificationScheduler(VerificationScheduler):
    version = "periodic_verification_scheduler_v1"

    def __init__(
        self,
        interval: int = 4,
        require_trigger: bool = True,
        require_selection: bool = True,
        require_target_frame: bool = True,
        fallback_when_missing_index: bool = True,
    ) -> None:
        self.interval = max(1, int(interval))
        self.require_trigger = require_trigger
        self.require_selection = require_selection
        self.require_target_frame = require_target_frame
        self.fallback_when_missing_index = fallback_when_missing_index

    def evaluate(
        self,
        candidate: DetectionCandidate,
        track: TrackState,
        source_frame: FramePacket,
        target_frame: FramePacket | None,
        trigger_decision: TriggerDecision,
        selected_for_verification: bool,
        environment: EnvironmentProfile,
    ) -> VerificationScheduleDecision:
        base = DefaultVerificationScheduler(
            require_trigger=self.require_trigger,
            require_selection=self.require_selection,
            require_target_frame=self.require_target_frame,
        ).evaluate(
            candidate=candidate,
            track=track,
            source_frame=source_frame,
            target_frame=target_frame,
            trigger_decision=trigger_decision,
            selected_for_verification=selected_for_verification,
            environment=environment,
        )
        if not base.should_verify:
            return base

        frame_index = _resolve_frame_index(source_frame)
        if frame_index is None:
            if self.fallback_when_missing_index:
                return VerificationScheduleDecision(
                    should_verify=True,
                    reason="periodic_scheduler_missing_index_fallback",
                    metadata={"interval": self.interval},
                )
            return VerificationScheduleDecision(
                should_verify=False,
                reason="frame_index_missing",
                metadata={"interval": self.interval},
            )
        if frame_index % self.interval != 0:
            return VerificationScheduleDecision(
                should_verify=False,
                reason="periodic_skip",
                metadata={"interval": self.interval, "frame_index": frame_index},
            )
        return VerificationScheduleDecision(
            should_verify=True,
            reason="periodic_fire",
            metadata={"interval": self.interval, "frame_index": frame_index},
        )


class BirdSahiAlwaysVerifyScheduler(VerificationScheduler):
    version = "bird_sahi_always_verify_scheduler_v1"

    def __init__(
        self,
        require_trigger: bool = True,
        require_selection: bool = True,
        require_target_frame: bool = True,
    ) -> None:
        self.require_trigger = require_trigger
        self.require_selection = require_selection
        self.require_target_frame = require_target_frame

    def evaluate(
        self,
        candidate: DetectionCandidate,
        track: TrackState,
        source_frame: FramePacket,
        target_frame: FramePacket | None,
        trigger_decision: TriggerDecision,
        selected_for_verification: bool,
        environment: EnvironmentProfile,
    ) -> VerificationScheduleDecision:
        if self.require_selection and not selected_for_verification:
            return VerificationScheduleDecision(
                should_verify=False,
                reason="not_selected_for_verification",
                metadata={"candidate_id": candidate.candidate_id},
            )
        if self.require_trigger and not trigger_decision.should_verify:
            return VerificationScheduleDecision(
                should_verify=False,
                reason=trigger_decision.trigger_reason,
                metadata=dict(trigger_decision.metadata),
            )
        if self.require_target_frame and target_frame is None:
            return VerificationScheduleDecision(
                should_verify=False,
                reason="target_frame_unavailable",
                metadata={"source_camera_id": source_frame.camera_id},
            )
        return VerificationScheduleDecision(
            should_verify=True,
            reason="forced_always_verify",
            metadata={
                "environment": environment.name,
                "selected_for_verification": selected_for_verification,
            },
        )


class BirdSahiKeyframeVerifyScheduler(VerificationScheduler):
    version = "bird_sahi_keyframe_verify_scheduler_v1"

    def __init__(
        self,
        interval: int = 4,
        require_trigger: bool = True,
        require_selection: bool = True,
        require_target_frame: bool = True,
        fallback_when_missing_index: bool = True,
        bootstrap_first_n: int = 0,
        use_track_local_index: bool = False,
    ) -> None:
        self.interval = max(1, int(interval))
        self.require_trigger = require_trigger
        self.require_selection = require_selection
        self.require_target_frame = require_target_frame
        self.fallback_when_missing_index = fallback_when_missing_index
        self.bootstrap_first_n = max(0, int(bootstrap_first_n))
        self.use_track_local_index = bool(use_track_local_index)
        self._track_observation_counts: dict[str, int] = {}

    def evaluate(
        self,
        candidate: DetectionCandidate,
        track: TrackState,
        source_frame: FramePacket,
        target_frame: FramePacket | None,
        trigger_decision: TriggerDecision,
        selected_for_verification: bool,
        environment: EnvironmentProfile,
    ) -> VerificationScheduleDecision:
        base = DefaultVerificationScheduler(
            require_trigger=self.require_trigger,
            require_selection=self.require_selection,
            require_target_frame=self.require_target_frame,
        ).evaluate(
            candidate=candidate,
            track=track,
            source_frame=source_frame,
            target_frame=target_frame,
            trigger_decision=trigger_decision,
            selected_for_verification=selected_for_verification,
            environment=environment,
        )
        if not base.should_verify:
            return base

        observation_index = self._track_observation_counts.get(track.track_id, 0) + 1
        self._track_observation_counts[track.track_id] = observation_index

        if self.bootstrap_first_n > 0 and observation_index <= self.bootstrap_first_n:
            return VerificationScheduleDecision(
                should_verify=True,
                reason="bird_sahi_bootstrap_verify",
                metadata={
                    "interval": self.interval,
                    "track_observation_index": observation_index,
                    "bootstrap_first_n": self.bootstrap_first_n,
                    "schedule_basis": "bootstrap",
                },
            )

        frame_index = _resolve_frame_index(source_frame)
        schedule_index = observation_index if self.use_track_local_index else frame_index
        schedule_basis = "track_local_index" if self.use_track_local_index else "frame_index"

        if schedule_index is None:
            if self.fallback_when_missing_index:
                return VerificationScheduleDecision(
                    should_verify=True,
                    reason="forced_keyframe_verify_missing_index_fallback",
                    metadata={
                        "interval": self.interval,
                        "frame_index": frame_index,
                        "track_observation_index": observation_index,
                        "schedule_basis": schedule_basis,
                    },
                )
            return VerificationScheduleDecision(
                should_verify=False,
                reason="frame_index_missing",
                metadata={
                    "interval": self.interval,
                    "frame_index": frame_index,
                    "track_observation_index": observation_index,
                    "schedule_basis": schedule_basis,
                },
            )
        if schedule_index % self.interval != 0:
            return VerificationScheduleDecision(
                should_verify=False,
                reason="forced_keyframe_skip",
                metadata={
                    "interval": self.interval,
                    "frame_index": frame_index,
                    "track_observation_index": observation_index,
                    "schedule_index": schedule_index,
                    "schedule_basis": schedule_basis,
                },
            )
        return VerificationScheduleDecision(
            should_verify=True,
            reason="forced_keyframe_verify",
            metadata={
                "interval": self.interval,
                "frame_index": frame_index,
                "track_observation_index": observation_index,
                "schedule_index": schedule_index,
                "schedule_basis": schedule_basis,
            },
        )


class NoOpConfirmationPolicy(ConfirmationPolicy):
    version = "noop_confirmation_policy_v1"

    def evaluate(
        self,
        candidate: DetectionCandidate,
        track: TrackState,
        verification: VerificationResult,
        source_frame: FramePacket,
        target_frame: FramePacket | None,
        environment: EnvironmentProfile,
    ) -> ConfirmationDecision:
        return ConfirmationDecision(
            confirmed=True,
            reason="confirmation_not_applied",
            metadata={"environment": environment.name},
        )


class TemporalStreakConfirmationPolicy(ConfirmationPolicy):
    version = "temporal_streak_confirmation_policy_v1"

    def __init__(
        self,
        confirm_after: int = 2,
        min_verifier_score: float = 0.0,
    ) -> None:
        self.confirm_after = max(1, int(confirm_after))
        self.min_verifier_score = float(min_verifier_score)
        self._streak_by_track: dict[str, int] = {}

    def evaluate(
        self,
        candidate: DetectionCandidate,
        track: TrackState,
        verification: VerificationResult,
        source_frame: FramePacket,
        target_frame: FramePacket | None,
        environment: EnvironmentProfile,
    ) -> ConfirmationDecision:
        meets_base = bool(verification.verified and verification.verifier_score >= self.min_verifier_score)
        streak = self._streak_by_track.get(track.track_id, 0)
        if meets_base:
            streak += 1
        else:
            streak = 0
        self._streak_by_track[track.track_id] = streak

        if streak >= self.confirm_after:
            return ConfirmationDecision(
                confirmed=True,
                reason="temporal_streak_met",
                metadata={"streak": streak, "confirm_after": self.confirm_after},
            )
        return ConfirmationDecision(
            confirmed=False,
            reason="temporal_streak_pending" if meets_base else "verification_not_confirmed",
            metadata={"streak": streak, "confirm_after": self.confirm_after},
        )


@dataclass(slots=True)
class _BirdSahiConfirmationState:
    bbox: DetectionCandidate | None = None
    track_id: str | None = None
    class_name: str = "target"
    streak: int = 0
    age: int = 0


class BirdSahiConfirmationPolicy(ConfirmationPolicy):
    version = "bird_sahi_confirmation_policy_v1"

    def __init__(
        self,
        confirm_iou: float = 0.4,
        confirm_len: int = 2,
        confirm_max_age: int = 2,
        min_verifier_score: float = 0.0,
    ) -> None:
        self.confirm_iou = float(confirm_iou)
        self.confirm_len = max(1, int(confirm_len))
        self.confirm_max_age = max(0, int(confirm_max_age))
        self.min_verifier_score = float(min_verifier_score)
        self._states: list[dict[str, Any]] = []

    def evaluate(
        self,
        candidate: DetectionCandidate,
        track: TrackState,
        verification: VerificationResult,
        source_frame: FramePacket,
        target_frame: FramePacket | None,
        environment: EnvironmentProfile,
    ) -> ConfirmationDecision:
        for state in self._states:
            state["age"] += 1

        bbox = verification.supporting_bbox or candidate.bbox
        if bbox is None:
            self._states = [state for state in self._states if state["age"] <= self.confirm_max_age]
            return ConfirmationDecision(
                confirmed=False,
                reason="bird_sahi_confirmation_missing_bbox",
                metadata={"confirm_len": self.confirm_len},
            )

        meets_base = bool(verification.verified and verification.verifier_score >= self.min_verifier_score)
        match_index = -1
        best_iou = 0.0
        for index, state in enumerate(self._states):
            state_bbox = state.get("bbox")
            if state.get("class_name") != candidate.class_name or state_bbox is None:
                continue
            iou_value = bbox_iou(bbox, state_bbox)
            if iou_value >= self.confirm_iou and iou_value > best_iou:
                best_iou = iou_value
                match_index = index

        if match_index >= 0:
            state = self._states[match_index]
            state["bbox"] = bbox
            state["track_id"] = track.track_id
            state["age"] = 0
            state["streak"] = state["streak"] + 1 if meets_base else 0
            streak = state["streak"]
        else:
            streak = 1 if meets_base else 0
            self._states.append(
                {
                    "bbox": bbox,
                    "track_id": track.track_id,
                    "class_name": candidate.class_name,
                    "streak": streak,
                    "age": 0,
                }
            )

        self._states = [state for state in self._states if state["age"] <= self.confirm_max_age]

        if streak >= self.confirm_len:
            return ConfirmationDecision(
                confirmed=True,
                reason="bird_sahi_confirmation_passed",
                metadata={
                    "streak": streak,
                    "confirm_len": self.confirm_len,
                    "confirm_iou": self.confirm_iou,
                },
            )
        return ConfirmationDecision(
            confirmed=False,
            reason="bird_sahi_confirmation_pending" if meets_base else "bird_sahi_confirmation_rejected",
            metadata={
                "streak": streak,
                "confirm_len": self.confirm_len,
                "confirm_iou": self.confirm_iou,
                "match_iou": best_iou,
            },
        )


def build_methodology_registries() -> tuple[FactoryRegistry, FactoryRegistry]:
    scheduler_registry = FactoryRegistry(expected_base=VerificationScheduler, kind="verification_scheduler")
    scheduler_registry.register(
        "default_verification_scheduler",
        lambda params: DefaultVerificationScheduler(
            require_trigger=bool(params.get("require_trigger", True)),
            require_selection=bool(params.get("require_selection", True)),
            require_target_frame=bool(params.get("require_target_frame", True)),
        ),
    )
    scheduler_registry.register(
        "periodic_verification_scheduler",
        lambda params: PeriodicVerificationScheduler(
            interval=int(params.get("interval", 4)),
            require_trigger=bool(params.get("require_trigger", True)),
            require_selection=bool(params.get("require_selection", True)),
            require_target_frame=bool(params.get("require_target_frame", True)),
            fallback_when_missing_index=bool(params.get("fallback_when_missing_index", True)),
        ),
    )
    scheduler_registry.register(
        "bird_sahi_always_verify_scheduler",
        lambda params: BirdSahiAlwaysVerifyScheduler(
            require_trigger=bool(params.get("require_trigger", True)),
            require_selection=bool(params.get("require_selection", True)),
            require_target_frame=bool(params.get("require_target_frame", True)),
        ),
    )
    scheduler_registry.register(
        "bird_sahi_keyframe_verify_scheduler",
        lambda params: BirdSahiKeyframeVerifyScheduler(
            interval=int(params.get("interval", 4)),
            require_trigger=bool(params.get("require_trigger", True)),
            require_selection=bool(params.get("require_selection", True)),
            require_target_frame=bool(params.get("require_target_frame", True)),
            fallback_when_missing_index=bool(params.get("fallback_when_missing_index", True)),
            bootstrap_first_n=int(params.get("bootstrap_first_n", 0)),
            use_track_local_index=bool(params.get("use_track_local_index", False)),
        ),
    )

    confirmation_registry = FactoryRegistry(expected_base=ConfirmationPolicy, kind="confirmation_policy")
    confirmation_registry.register(
        "noop_confirmation_policy",
        lambda params: NoOpConfirmationPolicy(),
    )
    confirmation_registry.register(
        "temporal_streak_confirmation_policy",
        lambda params: TemporalStreakConfirmationPolicy(
            confirm_after=int(params.get("confirm_after", 2)),
            min_verifier_score=float(params.get("min_verifier_score", 0.0)),
        ),
    )
    confirmation_registry.register(
        "bird_sahi_confirmation_policy",
        lambda params: BirdSahiConfirmationPolicy(
            confirm_iou=float(params.get("confirm_iou", 0.4)),
            confirm_len=int(params.get("confirm_len", 2)),
            confirm_max_age=int(params.get("confirm_max_age", 2)),
            min_verifier_score=float(params.get("min_verifier_score", 0.0)),
        ),
    )
    return scheduler_registry, confirmation_registry
