from __future__ import annotations

from thesis3.core import (
    ActionState,
    DecisionRecord,
    DetectionCandidate,
    LatencyBreakdown,
    PolicyConfig,
    TrackState,
    VerificationResult,
)


class PolicyGate:
    def __init__(self, config: PolicyConfig) -> None:
        self.config = config

    def decide(
        self,
        track: TrackState,
        candidate: DetectionCandidate,
        verification: VerificationResult | None,
        timestamp: float,
        latency: LatencyBreakdown | None = None,
        metadata: dict | None = None,
    ) -> DecisionRecord:
        reasons: list[str] = []
        policy_state = "rejected"
        action_state = ActionState.NO_ACTION
        human_review_required = False

        if verification is None:
            if candidate.detector_confidence >= self.config.review_threshold:
                policy_state = "review"
                action_state = ActionState.REVIEW_REQUIRED
                human_review_required = True
                reasons.append("verification_missing")
            else:
                reasons.append("stage1_confidence_too_low")
        else:
            quality_score = verification.quality_score if verification.quality_score is not None else 1.0
            if quality_score < self.config.quality_threshold:
                policy_state = "blocked"
                action_state = ActionState.BLOCKED_BY_SAFETY_GATE
                reasons.append("quality_below_gate")
            elif verification.verified and verification.verifier_score >= self.config.verification_threshold:
                policy_state = "accepted"
                action_state = ActionState.SIMULATED_ACTION
                reasons.append("verification_passed")
            elif verification.verifier_score >= self.config.review_threshold:
                policy_state = "review"
                action_state = ActionState.REVIEW_REQUIRED
                human_review_required = True
                reasons.append("verification_needs_review")
            else:
                reasons.append(verification.failure_reason or "verification_rejected")

        return DecisionRecord(
            track_id=track.track_id,
            stage1_summary={
                "candidate_id": candidate.candidate_id,
                "detector_confidence": candidate.detector_confidence,
                "class_name": candidate.class_name,
            },
            stage2_summary=(
                None
                if verification is None
                else {
                    "request_id": verification.request_id,
                    "verified": verification.verified,
                    "verifier_score": verification.verifier_score,
                    "quality_score": verification.quality_score,
                    "failure_reason": verification.failure_reason,
                }
            ),
            policy_state=policy_state,
            action_state=action_state,
            human_review_required=human_review_required,
            timestamp=timestamp,
            latency=latency,
            reasons=reasons,
            metadata=metadata or {},
        )
