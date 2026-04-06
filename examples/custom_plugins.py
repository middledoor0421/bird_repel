from __future__ import annotations

from time import perf_counter

from thesis3.components import Detector
from thesis3.core import BBox, DetectionCandidate, DetectorResult, FramePacket
from thesis3.methodology import (
    ConfirmationDecision,
    ConfirmationPolicy,
    VerificationScheduleDecision,
    VerificationScheduler,
)
from thesis3.orchestration import CandidateSelector, TriggerDecision, TriggerPolicy


class ExternalMetadataDetector(Detector):
    version = "external_metadata_detector_v1"

    def __init__(self, min_confidence: float = 0.5) -> None:
        self.min_confidence = min_confidence

    def detect(self, frame: FramePacket, roi: BBox | None = None) -> DetectorResult:
        started_at = perf_counter()
        candidates: list[DetectionCandidate] = []
        raw_candidates = frame.metadata.get("gt_objects")
        source = "gt_objects"
        if not raw_candidates:
            raw_candidates = frame.metadata.get("detections", [])
            source = "detections"
        for index, raw in enumerate(raw_candidates):
            bbox_raw = raw.get("bbox")
            if bbox_raw is None:
                continue
            score = float(raw.get("score", 0.95))
            if score < self.min_confidence:
                continue
            candidates.append(
                DetectionCandidate(
                    candidate_id=str(raw.get("object_id", f"{frame.frame_id}:external:{index}")),
                    frame_id=frame.frame_id,
                    camera_id=frame.camera_id,
                    bbox=BBox(*bbox_raw),
                    class_name=str(raw.get("class_name", "bird")),
                    detector_confidence=score,
                    detector_version=self.version,
                    metadata={"source": f"external_metadata_detector:{source}"},
                )
            )
        return DetectorResult(
            candidates=candidates,
            latency_ms=(perf_counter() - started_at) * 1000.0,
            diagnostics={"source": "external_plugin_file", "raw_source": source},
        )


class ExternalReviewBandTriggerPolicy(TriggerPolicy):
    version = "external_review_band_trigger_policy_v1"

    def __init__(self, min_confidence: float = 0.2, max_confidence: float = 0.95) -> None:
        self.min_confidence = min_confidence
        self.max_confidence = max_confidence

    def evaluate(
        self,
        candidate: DetectionCandidate,
        track,
        source_frame: FramePacket,
        target_frame: FramePacket | None,
    ) -> TriggerDecision:
        if target_frame is None:
            return TriggerDecision(False, "target_frame_unavailable")
        score = candidate.detector_confidence
        if score < self.min_confidence:
            return TriggerDecision(False, "below_external_band")
        if score > self.max_confidence:
            return TriggerDecision(False, "already_confident_external_band")
        return TriggerDecision(True, "external_band_verification")


class ExternalTopOneSelector(CandidateSelector):
    version = "external_top_one_selector_v1"

    def select(self, candidates, frame: FramePacket, max_candidates: int):
        if not candidates or max_candidates <= 0:
            return []
        ranked = sorted(candidates, key=lambda candidate: candidate.detector_confidence, reverse=True)
        return ranked[:1]


class ExternalConfidenceBandScheduler(VerificationScheduler):
    version = "external_confidence_band_scheduler_v1"

    def __init__(
        self,
        min_confidence: float = 0.4,
        max_confidence: float = 0.85,
        require_target_frame: bool = True,
        require_target_label: bool = True,
    ) -> None:
        self.min_confidence = min_confidence
        self.max_confidence = max_confidence
        self.require_target_frame = require_target_frame
        self.require_target_label = require_target_label

    def evaluate(
        self,
        candidate: DetectionCandidate,
        track,
        source_frame: FramePacket,
        target_frame: FramePacket | None,
        trigger_decision: TriggerDecision,
        selected_for_verification: bool,
        environment,
    ) -> VerificationScheduleDecision:
        if not selected_for_verification:
            return VerificationScheduleDecision(False, "external_scheduler_not_selected")
        if not trigger_decision.should_verify:
            return VerificationScheduleDecision(
                False,
                trigger_decision.trigger_reason,
                metadata=dict(trigger_decision.metadata),
            )
        if self.require_target_frame and target_frame is None:
            return VerificationScheduleDecision(False, "external_scheduler_target_frame_missing")
        if self.require_target_label and environment.target_labels:
            if candidate.class_name not in set(environment.target_labels):
                return VerificationScheduleDecision(
                    False,
                    "external_scheduler_non_target_label",
                    metadata={"class_name": candidate.class_name},
                )
        score = candidate.detector_confidence
        if score < self.min_confidence:
            return VerificationScheduleDecision(
                False,
                "external_scheduler_below_band",
                metadata={"score": score, "min_confidence": self.min_confidence},
            )
        if score > self.max_confidence:
            return VerificationScheduleDecision(
                False,
                "external_scheduler_already_confident",
                metadata={"score": score, "max_confidence": self.max_confidence},
            )
        return VerificationScheduleDecision(
            True,
            "external_scheduler_fire",
            metadata={
                "score": score,
                "target_labels": list(environment.target_labels),
                "track_id": track.track_id,
            },
        )


class ExternalEnvironmentConfirmationPolicy(ConfirmationPolicy):
    version = "external_environment_confirmation_policy_v1"

    def __init__(
        self,
        min_verifier_score: float = 0.7,
        min_track_confidence: float = 0.5,
        require_target_label: bool = True,
    ) -> None:
        self.min_verifier_score = min_verifier_score
        self.min_track_confidence = min_track_confidence
        self.require_target_label = require_target_label

    def evaluate(
        self,
        candidate: DetectionCandidate,
        track,
        verification,
        source_frame: FramePacket,
        target_frame: FramePacket | None,
        environment,
    ) -> ConfirmationDecision:
        if self.require_target_label and environment.target_labels:
            if candidate.class_name not in set(environment.target_labels):
                return ConfirmationDecision(
                    False,
                    "external_confirmation_non_target_label",
                    metadata={"class_name": candidate.class_name},
                )
        if not verification.verified:
            return ConfirmationDecision(
                False,
                "external_confirmation_unverified",
                metadata={"verifier_score": verification.verifier_score},
            )
        if verification.verifier_score < self.min_verifier_score:
            return ConfirmationDecision(
                False,
                "external_confirmation_score_too_low",
                metadata={
                    "verifier_score": verification.verifier_score,
                    "min_verifier_score": self.min_verifier_score,
                },
            )
        if track.track_confidence < self.min_track_confidence:
            return ConfirmationDecision(
                False,
                "external_confirmation_track_too_weak",
                metadata={
                    "track_confidence": track.track_confidence,
                    "min_track_confidence": self.min_track_confidence,
                },
            )
        return ConfirmationDecision(
            True,
            "external_confirmation_passed",
            metadata={
                "environment": environment.name,
                "track_confidence": track.track_confidence,
                "verifier_score": verification.verifier_score,
            },
        )
