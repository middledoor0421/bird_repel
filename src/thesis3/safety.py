from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from thesis3.core import (
    ActionState,
    BBox,
    DecisionRecord,
    DetectionCandidate,
    EnvironmentProfile,
    FactoryRegistry,
    FramePacket,
    TrackState,
    VerificationResult,
)
from thesis3.dataclass_compat import dataclass, field
from thesis3.image_io import bbox_iou


@dataclass(slots=True)
class SafetyPolicyDecision:
    should_override: bool
    reason: str
    action_state: ActionState | None = None
    policy_state: str | None = None
    human_review_required: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class SafetyPolicy(ABC):
    version: str

    @abstractmethod
    def evaluate(
        self,
        decision: DecisionRecord,
        candidate: DetectionCandidate,
        track: TrackState,
        verification: VerificationResult | None,
        source_frame: FramePacket,
        target_frame: FramePacket | None,
        environment: EnvironmentProfile,
    ) -> SafetyPolicyDecision:
        raise NotImplementedError


class NoOpSafetyPolicy(SafetyPolicy):
    version = "noop_safety_policy_v1"

    def evaluate(
        self,
        decision: DecisionRecord,
        candidate: DetectionCandidate,
        track: TrackState,
        verification: VerificationResult | None,
        source_frame: FramePacket,
        target_frame: FramePacket | None,
        environment: EnvironmentProfile,
    ) -> SafetyPolicyDecision:
        return SafetyPolicyDecision(
            should_override=False,
            reason="safety_policy_not_applied",
            metadata={"environment": environment.name},
        )


class CCSLCSSafetyPolicy(SafetyPolicy):
    version = "ccs_lcs_safety_policy_v1"

    def __init__(
        self,
        min_verifier_score: float = 0.7,
        non_target_score_threshold: float = 0.4,
        temporal_k_confirm: int = 2,
        safe_idle_on_uncertainty: bool = True,
        uncertainty_threshold: float = 0.35,
        require_safe_zone: bool = True,
        min_non_target_iou: float = 0.0,
        only_override_simulated_action: bool = True,
    ) -> None:
        self.min_verifier_score = float(min_verifier_score)
        self.non_target_score_threshold = float(non_target_score_threshold)
        self.temporal_k_confirm = max(1, int(temporal_k_confirm))
        self.safe_idle_on_uncertainty = bool(safe_idle_on_uncertainty)
        self.uncertainty_threshold = float(uncertainty_threshold)
        self.require_safe_zone = bool(require_safe_zone)
        self.min_non_target_iou = float(min_non_target_iou)
        self.only_override_simulated_action = bool(only_override_simulated_action)
        self._confirm_streak_by_track: dict[str, int] = {}

    def evaluate(
        self,
        decision: DecisionRecord,
        candidate: DetectionCandidate,
        track: TrackState,
        verification: VerificationResult | None,
        source_frame: FramePacket,
        target_frame: FramePacket | None,
        environment: EnvironmentProfile,
    ) -> SafetyPolicyDecision:
        if self.only_override_simulated_action and decision.action_state != ActionState.SIMULATED_ACTION:
            return SafetyPolicyDecision(
                should_override=False,
                reason="safety_policy_skipped_non_actionable_state",
                metadata={"action_state": decision.action_state.value},
            )

        if verification is None:
            self._confirm_streak_by_track[track.track_id] = 0
            return self._blocked(
                reason="verification_missing",
                metadata={"track_id": track.track_id},
            )

        if self.safe_idle_on_uncertainty and verification.uncertainty is not None:
            if float(verification.uncertainty) >= self.uncertainty_threshold:
                self._confirm_streak_by_track[track.track_id] = 0
                return self._blocked(
                    reason="uncertainty",
                    metadata={
                        "uncertainty": verification.uncertainty,
                        "uncertainty_threshold": self.uncertainty_threshold,
                    },
                )

        target_labels = {label.lower() for label in environment.target_labels}
        non_target_labels = {label.lower() for label in environment.non_target_labels}
        target_confirmed = bool(
            verification.verified
            and verification.verifier_score >= self.min_verifier_score
            and (not target_labels or candidate.class_name.lower() in target_labels)
        )
        non_target_absent, offender = self._non_target_absent(
            frame=source_frame,
            candidate_bbox=candidate.bbox,
            non_target_labels=non_target_labels,
        )
        within_safe_zone = self._within_safe_zone(candidate.bbox, source_frame, environment.safe_zone)

        base_pass = bool(target_confirmed and non_target_absent and within_safe_zone)
        if base_pass:
            streak = self._confirm_streak_by_track.get(track.track_id, 0) + 1
        else:
            streak = 0
        self._confirm_streak_by_track[track.track_id] = streak
        temporal_ok = streak >= self.temporal_k_confirm

        if base_pass and temporal_ok:
            return SafetyPolicyDecision(
                should_override=False,
                reason="ccs_lcs_allow",
                metadata={
                    "target_confirmed": target_confirmed,
                    "non_target_absent": non_target_absent,
                    "within_safe_zone": within_safe_zone,
                    "temporal_consistency": temporal_ok,
                    "streak": streak,
                },
            )

        if not target_confirmed:
            reason = "target_not_confirmed"
        elif not non_target_absent:
            reason = "non_target_present"
        elif not within_safe_zone:
            reason = "out_of_safe_zone"
        else:
            reason = "temporal_consistency"
        return self._blocked(
            reason=reason,
            metadata={
                "target_confirmed": target_confirmed,
                "non_target_absent": non_target_absent,
                "within_safe_zone": within_safe_zone,
                "temporal_consistency": temporal_ok,
                "streak": streak,
                "temporal_k_confirm": self.temporal_k_confirm,
                "offender": offender,
            },
        )

    def _blocked(self, reason: str, metadata: dict[str, Any]) -> SafetyPolicyDecision:
        return SafetyPolicyDecision(
            should_override=True,
            reason=reason,
            action_state=ActionState.BLOCKED_BY_SAFETY_GATE,
            policy_state="blocked",
            human_review_required=False,
            metadata=metadata,
        )

    def _non_target_absent(
        self,
        frame: FramePacket,
        candidate_bbox: BBox | None,
        non_target_labels: set[str],
    ) -> tuple[bool, dict[str, Any] | None]:
        if not non_target_labels:
            return True, None
        for key in ("detections", "gt_objects"):
            for raw in frame.metadata.get(key, []):
                label = str(raw.get("class_name", "")).lower()
                if label not in non_target_labels:
                    continue
                score = float(raw.get("score", raw.get("detector_confidence", 1.0)))
                if score < self.non_target_score_threshold:
                    continue
                bbox_raw = raw.get("bbox")
                raw_bbox = None
                if bbox_raw is not None and len(bbox_raw) == 4:
                    raw_bbox = BBox(*[float(value) for value in bbox_raw])
                if candidate_bbox is not None and raw_bbox is not None:
                    if bbox_iou(candidate_bbox, raw_bbox) < self.min_non_target_iou:
                        continue
                return False, {
                    "label": label,
                    "score": score,
                    "source": key,
                }
        return True, None

    def _within_safe_zone(
        self,
        candidate_bbox: BBox | None,
        frame: FramePacket,
        safe_zone: dict[str, Any],
    ) -> bool:
        if not self.require_safe_zone:
            return True
        if candidate_bbox is None:
            return False
        zone_bbox = safe_zone.get("bbox")
        if not zone_bbox or len(zone_bbox) != 4:
            return True
        zone = BBox(*[float(value) for value in zone_bbox])
        center_x = (candidate_bbox.x1 + candidate_bbox.x2) / 2.0
        center_y = (candidate_bbox.y1 + candidate_bbox.y2) / 2.0
        return bool(zone.x1 <= center_x <= zone.x2 and zone.y1 <= center_y <= zone.y2)


def build_safety_registry() -> FactoryRegistry:
    registry = FactoryRegistry(expected_base=SafetyPolicy, kind="safety_policy")
    registry.register("noop_safety_policy", lambda params: NoOpSafetyPolicy())
    registry.register(
        "ccs_lcs_safety_policy",
        lambda params: CCSLCSSafetyPolicy(
            min_verifier_score=float(params.get("min_verifier_score", 0.7)),
            non_target_score_threshold=float(params.get("non_target_score_threshold", 0.4)),
            temporal_k_confirm=int(params.get("temporal_k_confirm", 2)),
            safe_idle_on_uncertainty=bool(params.get("safe_idle_on_uncertainty", True)),
            uncertainty_threshold=float(params.get("uncertainty_threshold", 0.35)),
            require_safe_zone=bool(params.get("require_safe_zone", True)),
            min_non_target_iou=float(params.get("min_non_target_iou", 0.0)),
            only_override_simulated_action=bool(params.get("only_override_simulated_action", True)),
        ),
    )
    return registry
