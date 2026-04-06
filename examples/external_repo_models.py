from __future__ import annotations

from typing import Any


class DemoForeignDetectorModel:
    def __init__(self, min_confidence: float = 0.4) -> None:
        self.min_confidence = min_confidence

    def predict(self, frame_packet, roi=None) -> dict[str, Any]:
        detections: list[dict[str, Any]] = []
        for index, raw in enumerate(frame_packet.metadata.get("detections", [])):
            score = float(raw.get("score", 0.0))
            if score < self.min_confidence:
                continue
            detections.append(
                {
                    "candidate_id": raw.get("candidate_id", f"{frame_packet.frame_id}:foreign:{index}"),
                    "bbox": raw.get("bbox"),
                    "label": raw.get("class_name", "bird"),
                    "score": score,
                    "object_id": raw.get("object_id"),
                    "source": "demo_foreign_detector_model",
                }
            )
        return {"predictions": detections}


class DemoForeignVerifierModel:
    def __init__(self, candidate_weight: float = 0.6) -> None:
        self.candidate_weight = candidate_weight

    def score(self, frame_packet, request=None, context=None) -> dict[str, Any]:
        quality = 0.0
        if frame_packet is not None:
            quality = float(frame_packet.metadata.get("quality_score", 0.0))
        candidate_confidence = 0.0
        if request is not None:
            candidate_confidence = float(request.metadata.get("candidate_confidence", 0.0))
        explicit_score = None
        if frame_packet is not None:
            explicit_score = frame_packet.metadata.get("verification_score")
        score = (
            float(explicit_score)
            if explicit_score is not None
            else (candidate_confidence * self.candidate_weight) + (quality * (1.0 - self.candidate_weight))
        )
        verified = score >= 0.7 and quality >= 0.3
        return {
            "result": {
                "verified": verified,
                "score": score,
                "quality": quality,
                "failure_reason": None if verified else "demo_foreign_model_reject",
                "metadata": {
                    "context_frames": len(context or []),
                    "source": "demo_foreign_verifier_model",
                },
            }
        }
