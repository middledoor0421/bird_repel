from __future__ import annotations

from time import perf_counter

from thesis3.components import Detector, Tracker, Verifier
from thesis3.core import (
    BBox,
    DecisionRecord,
    FramePacket,
    LatencyBreakdown,
    PipelineConfig,
    TrackState,
    VerificationRequest,
)
from thesis3.events import JsonlEventStore
from thesis3.methodology import ConfirmationPolicy, VerificationScheduler
from thesis3.orchestration import CandidateSelector, TriggerPolicy
from thesis3.policy import PolicyGate
from thesis3.safety import SafetyPolicy, SafetyPolicyDecision
from thesis3.simulation import ActuatorSimulator
from thesis3.dataclass_compat import dataclass, replace


@dataclass(slots=True)
class PipelineContext:
    config: PipelineConfig
    run_id: str
    detector: Detector
    verifier: Verifier | None
    tracker: Tracker
    trigger_policy: TriggerPolicy
    candidate_selector: CandidateSelector
    verification_scheduler: VerificationScheduler
    confirmation_policy: ConfirmationPolicy
    safety_policy: SafetyPolicy
    policy_gate: PolicyGate
    actuator: ActuatorSimulator
    event_store: JsonlEventStore

    def log(self, event_type: str, payload: object, timestamp: float | None = None) -> None:
        self.event_store.append(event_type, payload, timestamp=timestamp)


class ScenarioAPipeline:
    def __init__(self, context: PipelineContext) -> None:
        self.context = context
        self.primary_camera_id = self._camera_for_roles({"primary", "central", "wide"})
        self.verification_camera_id = self._camera_for_roles({"verification", "stage2", "tele", "zoom"})

    def _camera_for_roles(self, roles: set[str]) -> str | None:
        for camera in self.context.config.cameras:
            if camera.role in roles:
                return camera.camera_id
        return None

    def process_group(self, packets: list[FramePacket]) -> list[DecisionRecord]:
        packet_map = {packet.camera_id: packet for packet in packets}
        primary_frame = packet_map.get(self.primary_camera_id or "", packets[0] if packets else None)
        if primary_frame is None:
            return []

        verification_frame = packet_map.get(self.verification_camera_id or "")
        detector_started_at = perf_counter()
        detector_result = self.context.detector.detect(primary_frame)
        detector_wall_latency_ms = (perf_counter() - detector_started_at) * 1000.0
        detector_latency_ms = self._resolved_stage_latency_ms(
            detector_result.latency_ms,
            detector_wall_latency_ms,
        )
        self.context.log(
            "detector_result",
            {
                "frame_id": primary_frame.frame_id,
                "camera_id": primary_frame.camera_id,
                "image_ref": primary_frame.image_ref,
                "timestamp": primary_frame.timestamp,
                "result": detector_result,
            },
            primary_frame.timestamp,
        )

        tracker_started_at = perf_counter()
        tracker_update = self.context.tracker.update(detector_result.candidates, primary_frame)
        tracker_wall_latency_ms = (perf_counter() - tracker_started_at) * 1000.0
        tracker_latency_ms = self._resolved_stage_latency_ms(
            tracker_update.latency_ms,
            tracker_wall_latency_ms,
        )
        self.context.log("tracker_update", tracker_update, primary_frame.timestamp)
        verification_requested = 0

        candidates = {candidate.candidate_id: candidate for candidate in detector_result.candidates}
        decisions: list[DecisionRecord] = []

        for track in tracker_update.tracks:
            latest_candidate = candidates.get(track.candidate_ids[-1])
            if latest_candidate is None:
                continue

            verification = None
            verification_latency_ms = None
            confirmation_decision = None
            trigger_decision = self.context.trigger_policy.evaluate(
                candidate=latest_candidate,
                track=track,
                source_frame=primary_frame,
                target_frame=verification_frame,
            )
            self.context.log("trigger_decision", trigger_decision, primary_frame.timestamp)
            schedule_decision = self.context.verification_scheduler.evaluate(
                candidate=latest_candidate,
                track=track,
                source_frame=primary_frame,
                target_frame=verification_frame,
                trigger_decision=trigger_decision,
                selected_for_verification=True,
                environment=self.context.config.environment,
            )
            self.context.log("verification_schedule", schedule_decision, primary_frame.timestamp)
            if self.context.verifier is not None and schedule_decision.should_verify:
                verification_requested += 1
                request = VerificationRequest(
                    request_id=f"req-{latest_candidate.candidate_id}",
                    source_track_id=track.track_id,
                    source_camera_id=primary_frame.camera_id,
                    target_camera_id=(
                        verification_frame.camera_id if verification_frame is not None else self.verification_camera_id or "unassigned"
                    ),
                    roi_hint=latest_candidate.bbox,
                    trigger_reason=trigger_decision.trigger_reason,
                    deadline_ms=int(self.context.config.extra.get("verification_deadline_ms", 250)),
                    metadata={
                        "candidate_confidence": latest_candidate.detector_confidence,
                        "class_name": latest_candidate.class_name,
                        "candidate_id": latest_candidate.candidate_id,
                        "verification_schedule_reason": schedule_decision.reason,
                        **dict(trigger_decision.metadata),
                        **dict(schedule_decision.metadata),
                    },
                )
                self.context.log("verification_request", request, primary_frame.timestamp)
                verification_started_at = perf_counter()
                verification = self.context.verifier.verify(request, verification_frame)
                verification_wall_latency_ms = (perf_counter() - verification_started_at) * 1000.0
                verification_latency_ms = self._resolved_stage_latency_ms(
                    verification.latency_ms,
                    verification_wall_latency_ms,
                )
                verification.latency_ms = verification_latency_ms
                self.context.log("verification_result", verification, verification_frame.timestamp)
                confirmation_decision = self.context.confirmation_policy.evaluate(
                    candidate=latest_candidate,
                    track=track,
                    verification=verification,
                    source_frame=primary_frame,
                    target_frame=verification_frame,
                    environment=self.context.config.environment,
                )
                self.context.log("confirmation_decision", confirmation_decision, primary_frame.timestamp)
                if not confirmation_decision.confirmed:
                    verification = replace(
                        verification,
                        verified=False,
                        failure_reason=confirmation_decision.reason,
                        metadata={
                            **verification.metadata,
                            "confirmation_reason": confirmation_decision.reason,
                            "confirmation": dict(confirmation_decision.metadata),
                        },
                    )

            decision_timestamp = verification_frame.timestamp if verification is not None and verification_frame else primary_frame.timestamp
            policy_started_at = perf_counter()
            decision_metadata = {
                "scenario": self.context.config.scenario,
                "environment_profile": self.context.config.environment.name,
                "source_camera_id": primary_frame.camera_id,
                "verification_camera_id": verification_frame.camera_id if verification_frame else None,
                "group_packet_count": len(packets),
                "tick_candidate_count": len(detector_result.candidates),
                "verification_requested_count": verification_requested,
                "trigger_reason": trigger_decision.trigger_reason,
                "verification_schedule_reason": schedule_decision.reason,
                "confirmation_reason": None if confirmation_decision is None else confirmation_decision.reason,
            }
            latency = LatencyBreakdown(
                detector_latency_ms=detector_latency_ms,
                tracker_latency_ms=tracker_latency_ms,
                verification_latency_ms=verification_latency_ms,
                source_to_decision_latency_ms=max(0.0, (decision_timestamp - primary_frame.timestamp) * 1000.0),
            )
            decision = self.context.policy_gate.decide(
                track=track,
                candidate=latest_candidate,
                verification=verification,
                timestamp=decision_timestamp,
                latency=latency,
                metadata=decision_metadata,
            )
            safety_decision = self.context.safety_policy.evaluate(
                decision=decision,
                candidate=latest_candidate,
                track=track,
                verification=verification,
                source_frame=primary_frame,
                target_frame=verification_frame,
                environment=self.context.config.environment,
            )
            self.context.log("safety_policy_decision", safety_decision, primary_frame.timestamp)
            decision = self._apply_safety_policy(decision, safety_decision)
            decision.latency.policy_latency_ms = (perf_counter() - policy_started_at) * 1000.0

            actuator_started_at = perf_counter()
            actuator_result = self.context.actuator.dispatch(decision)
            actuator_latency_ms = (perf_counter() - actuator_started_at) * 1000.0
            decision.latency.actuator_latency_ms = actuator_latency_ms if actuator_result is not None else 0.0
            decision.latency.end_to_end_compute_latency_ms = self._sum_defined_latencies(
                decision.latency.detector_latency_ms,
                decision.latency.tracker_latency_ms,
                decision.latency.verification_latency_ms,
                decision.latency.policy_latency_ms,
                decision.latency.actuator_latency_ms,
            )
            if actuator_result is not None:
                self.context.log("actuator_result", actuator_result, primary_frame.timestamp)
            self.context.log("decision_record", decision, primary_frame.timestamp)
            self.context.log("decision_metrics", decision.latency, primary_frame.timestamp)
            decisions.append(decision)

        self.context.log(
            "tick_summary",
            {
                "scenario": self.context.config.scenario,
                "timestamp": primary_frame.timestamp,
                "group_packet_count": len(packets),
                "candidate_count": len(detector_result.candidates),
                "track_count": len(tracker_update.tracks),
                "verification_requested_count": verification_requested,
                "decision_count": len(decisions),
                "detector_latency_ms": detector_latency_ms,
                "tracker_latency_ms": tracker_latency_ms,
            },
            primary_frame.timestamp,
        )
        return decisions

    def _resolved_stage_latency_ms(self, reported_latency_ms: float | None, wall_latency_ms: float) -> float:
        if reported_latency_ms is not None and reported_latency_ms > 0.0:
            return reported_latency_ms
        return wall_latency_ms

    def _sum_defined_latencies(self, *values: float | None) -> float:
        return sum(value for value in values if value is not None)

    def _apply_safety_policy(
        self,
        decision: DecisionRecord,
        safety_decision: SafetyPolicyDecision,
    ) -> DecisionRecord:
        metadata = {
            **decision.metadata,
            "safety_policy_reason": safety_decision.reason,
            "safety_policy": dict(safety_decision.metadata),
        }
        if not safety_decision.should_override:
            return replace(decision, metadata=metadata)
        return replace(
            decision,
            policy_state=safety_decision.policy_state or decision.policy_state,
            action_state=safety_decision.action_state or decision.action_state,
            human_review_required=(
                decision.human_review_required
                if safety_decision.human_review_required is None
                else safety_decision.human_review_required
            ),
            reasons=[*decision.reasons, safety_decision.reason],
            metadata=metadata,
        )


class ScenarioBPipeline:
    def __init__(self, context: PipelineContext) -> None:
        self.context = context
        self.wide_camera_id = self._camera_for_roles({"wide", "primary", "central"})
        self.zoom_camera_id = self._camera_for_roles({"zoom", "tele", "verification"})

    def _camera_for_roles(self, roles: set[str]) -> str | None:
        for camera in self.context.config.cameras:
            if camera.role in roles:
                return camera.camera_id
        return None

    def process_group(self, packets: list[FramePacket]) -> list[DecisionRecord]:
        packet_map = {packet.camera_id: packet for packet in packets}
        wide_frame = packet_map.get(self.wide_camera_id or "", packets[0] if packets else None)
        if wide_frame is None:
            return []

        zoom_frame = packet_map.get(self.zoom_camera_id or "")
        detector_started_at = perf_counter()
        detector_result = self.context.detector.detect(wide_frame)
        detector_wall_latency_ms = (perf_counter() - detector_started_at) * 1000.0
        detector_latency_ms = self._resolved_stage_latency_ms(
            detector_result.latency_ms,
            detector_wall_latency_ms,
        )
        self.context.log(
            "detector_result",
            {
                "frame_id": wide_frame.frame_id,
                "camera_id": wide_frame.camera_id,
                "image_ref": wide_frame.image_ref,
                "timestamp": wide_frame.timestamp,
                "result": detector_result,
            },
            wide_frame.timestamp,
        )

        tracker_started_at = perf_counter()
        tracker_update = self.context.tracker.update(detector_result.candidates, wide_frame)
        tracker_wall_latency_ms = (perf_counter() - tracker_started_at) * 1000.0
        tracker_latency_ms = self._resolved_stage_latency_ms(
            tracker_update.latency_ms,
            tracker_wall_latency_ms,
        )
        self.context.log("tracker_update", tracker_update, wide_frame.timestamp)

        selected_candidates = self.context.candidate_selector.select(
            detector_result.candidates,
            wide_frame,
            self.context.config.policy.max_candidates_per_tick,
        )
        self.context.log(
            "candidate_selection",
            {
                "selected_candidate_ids": [candidate.candidate_id for candidate in selected_candidates],
                "selected_count": len(selected_candidates),
                "input_count": len(detector_result.candidates),
            },
            wide_frame.timestamp,
        )
        selected_ids = {candidate.candidate_id for candidate in selected_candidates}
        candidates = {candidate.candidate_id: candidate for candidate in detector_result.candidates}
        decisions: list[DecisionRecord] = []
        verification_requested = 0

        for track in tracker_update.tracks:
            latest_candidate = candidates.get(track.candidate_ids[-1])
            if latest_candidate is None:
                continue

            verification = None
            verification_latency_ms = None
            confirmation_decision = None
            trigger_decision = self.context.trigger_policy.evaluate(
                candidate=latest_candidate,
                track=track,
                source_frame=wide_frame,
                target_frame=zoom_frame,
            )
            self.context.log("trigger_decision", trigger_decision, wide_frame.timestamp)
            schedule_decision = self.context.verification_scheduler.evaluate(
                candidate=latest_candidate,
                track=track,
                source_frame=wide_frame,
                target_frame=zoom_frame,
                trigger_decision=trigger_decision,
                selected_for_verification=latest_candidate.candidate_id in selected_ids,
                environment=self.context.config.environment,
            )
            self.context.log("verification_schedule", schedule_decision, wide_frame.timestamp)
            if (
                self.context.verifier is not None
                and schedule_decision.should_verify
            ):
                verification_requested += 1
                request = VerificationRequest(
                    request_id=f"req-{latest_candidate.candidate_id}",
                    source_track_id=track.track_id,
                    source_camera_id=wide_frame.camera_id,
                    target_camera_id=zoom_frame.camera_id if zoom_frame is not None else self.zoom_camera_id or "unassigned",
                    roi_hint=latest_candidate.bbox,
                    trigger_reason=trigger_decision.trigger_reason,
                    deadline_ms=int(self.context.config.extra.get("verification_deadline_ms", 250)),
                    metadata={
                        "candidate_confidence": latest_candidate.detector_confidence,
                        "class_name": latest_candidate.class_name,
                        "candidate_id": latest_candidate.candidate_id,
                        "verification_schedule_reason": schedule_decision.reason,
                        **dict(trigger_decision.metadata),
                        **dict(schedule_decision.metadata),
                    },
                )
                self.context.log("verification_request", request, wide_frame.timestamp)
                verification_started_at = perf_counter()
                verification = self.context.verifier.verify(request, zoom_frame)
                verification_wall_latency_ms = (perf_counter() - verification_started_at) * 1000.0
                verification_latency_ms = self._resolved_stage_latency_ms(
                    verification.latency_ms,
                    verification_wall_latency_ms,
                )
                verification.latency_ms = verification_latency_ms
                self.context.log("verification_result", verification, zoom_frame.timestamp)
                confirmation_decision = self.context.confirmation_policy.evaluate(
                    candidate=latest_candidate,
                    track=track,
                    verification=verification,
                    source_frame=wide_frame,
                    target_frame=zoom_frame,
                    environment=self.context.config.environment,
                )
                self.context.log("confirmation_decision", confirmation_decision, wide_frame.timestamp)
                if not confirmation_decision.confirmed:
                    verification = replace(
                        verification,
                        verified=False,
                        failure_reason=confirmation_decision.reason,
                        metadata={
                            **verification.metadata,
                            "confirmation_reason": confirmation_decision.reason,
                            "confirmation": dict(confirmation_decision.metadata),
                        },
                    )

            decision_timestamp = zoom_frame.timestamp if verification is not None and zoom_frame else wide_frame.timestamp
            policy_started_at = perf_counter()
            decision_metadata = {
                "scenario": self.context.config.scenario,
                "environment_profile": self.context.config.environment.name,
                "source_camera_id": wide_frame.camera_id,
                "verification_camera_id": zoom_frame.camera_id if zoom_frame else None,
                "group_packet_count": len(packets),
                "tick_candidate_count": len(detector_result.candidates),
                "verification_requested_count": verification_requested,
                "selected_candidate_count": len(selected_candidates),
                "trigger_reason": trigger_decision.trigger_reason,
                "verification_schedule_reason": schedule_decision.reason,
                "confirmation_reason": None if confirmation_decision is None else confirmation_decision.reason,
            }
            latency = LatencyBreakdown(
                detector_latency_ms=detector_latency_ms,
                tracker_latency_ms=tracker_latency_ms,
                verification_latency_ms=verification_latency_ms,
                source_to_decision_latency_ms=max(0.0, (decision_timestamp - wide_frame.timestamp) * 1000.0),
            )
            decision = self.context.policy_gate.decide(
                track=track,
                candidate=latest_candidate,
                verification=verification,
                timestamp=decision_timestamp,
                latency=latency,
                metadata=decision_metadata,
            )
            safety_decision = self.context.safety_policy.evaluate(
                decision=decision,
                candidate=latest_candidate,
                track=track,
                verification=verification,
                source_frame=wide_frame,
                target_frame=zoom_frame,
                environment=self.context.config.environment,
            )
            self.context.log("safety_policy_decision", safety_decision, wide_frame.timestamp)
            decision = self._apply_safety_policy(decision, safety_decision)
            decision.latency.policy_latency_ms = (perf_counter() - policy_started_at) * 1000.0

            actuator_started_at = perf_counter()
            actuator_result = self.context.actuator.dispatch(decision)
            actuator_latency_ms = (perf_counter() - actuator_started_at) * 1000.0
            decision.latency.actuator_latency_ms = actuator_latency_ms if actuator_result is not None else 0.0
            decision.latency.end_to_end_compute_latency_ms = self._sum_defined_latencies(
                decision.latency.detector_latency_ms,
                decision.latency.tracker_latency_ms,
                decision.latency.verification_latency_ms,
                decision.latency.policy_latency_ms,
                decision.latency.actuator_latency_ms,
            )
            if actuator_result is not None:
                self.context.log("actuator_result", actuator_result, wide_frame.timestamp)
            self.context.log("decision_record", decision, wide_frame.timestamp)
            self.context.log("decision_metrics", decision.latency, wide_frame.timestamp)
            decisions.append(decision)

        self.context.log(
            "tick_summary",
            {
                "scenario": self.context.config.scenario,
                "timestamp": wide_frame.timestamp,
                "group_packet_count": len(packets),
                "candidate_count": len(detector_result.candidates),
                "selected_candidate_count": len(selected_candidates),
                "track_count": len(tracker_update.tracks),
                "verification_requested_count": verification_requested,
                "decision_count": len(decisions),
                "detector_latency_ms": detector_latency_ms,
                "tracker_latency_ms": tracker_latency_ms,
            },
            wide_frame.timestamp,
        )
        return decisions

    def _resolved_stage_latency_ms(self, reported_latency_ms: float | None, wall_latency_ms: float) -> float:
        if reported_latency_ms is not None and reported_latency_ms > 0.0:
            return reported_latency_ms
        return wall_latency_ms

    def _sum_defined_latencies(self, *values: float | None) -> float:
        return sum(value for value in values if value is not None)

    def _apply_safety_policy(
        self,
        decision: DecisionRecord,
        safety_decision: SafetyPolicyDecision,
    ) -> DecisionRecord:
        metadata = {
            **decision.metadata,
            "safety_policy_reason": safety_decision.reason,
            "safety_policy": dict(safety_decision.metadata),
        }
        if not safety_decision.should_override:
            return replace(decision, metadata=metadata)
        return replace(
            decision,
            policy_state=safety_decision.policy_state or decision.policy_state,
            action_state=safety_decision.action_state or decision.action_state,
            human_review_required=(
                decision.human_review_required
                if safety_decision.human_review_required is None
                else safety_decision.human_review_required
            ),
            reasons=[*decision.reasons, safety_decision.reason],
            metadata=metadata,
        )


def build_pipeline(context: PipelineContext) -> ScenarioAPipeline | ScenarioBPipeline:
    if context.config.scenario == "scenario_a":
        return ScenarioAPipeline(context)
    if context.config.scenario == "scenario_b":
        return ScenarioBPipeline(context)
    raise ValueError(f"Unsupported scenario: {context.config.scenario}")
