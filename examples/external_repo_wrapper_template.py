from __future__ import annotations

from time import perf_counter
from typing import Any

from thesis3.components import Detector, Verifier
from thesis3.core import BBox, DetectorResult, FramePacket, VerificationRequest, VerificationResult
from thesis3.external_adapters import ExternalAdapterSupport


class TemplateRepoDetectorWrapper(ExternalAdapterSupport, Detector):
    version = "template_repo_detector_wrapper_v1"

    def __init__(
        self,
        model_target: str = "./examples/external_repo_models.py:DemoForeignDetectorModel",
        model_init_params: dict[str, Any] | None = None,
        min_confidence: float = 0.4,
    ) -> None:
        self.model = self.instantiate_external_symbol(model_target, model_init_params or {})
        self.min_confidence = min_confidence

    def detect(self, frame: FramePacket, roi: BBox | None = None) -> DetectorResult:
        started_at = perf_counter()

        # TODO:
        # 1. Replace this call with the real foreign repo's inference API.
        # 2. If the foreign model expects an image path or numpy array instead of FramePacket,
        #    use build_frame_input(frame, "image_path" | "numpy_rgb" | "roi_array", roi).
        raw_output = self.model.predict(frame, roi=roi)
        raw_detections = raw_output.get("predictions", [])

        candidates = []
        for index, raw in enumerate(raw_detections):
            candidate = self.build_detection_candidate(
                raw,
                frame=frame,
                index=index,
                detector_version=self.version,
                class_name_key="label",
            )
            if candidate.detector_confidence >= self.min_confidence:
                candidates.append(candidate)

        return DetectorResult(
            candidates=candidates,
            latency_ms=(perf_counter() - started_at) * 1000.0,
            diagnostics={"source": "template_external_detector_wrapper"},
        )


class TemplateRepoVerifierWrapper(ExternalAdapterSupport, Verifier):
    version = "template_repo_verifier_wrapper_v1"

    def __init__(
        self,
        model_target: str = "./examples/external_repo_models.py:DemoForeignVerifierModel",
        model_init_params: dict[str, Any] | None = None,
        score_threshold: float = 0.7,
    ) -> None:
        self.model = self.instantiate_external_symbol(model_target, model_init_params or {})
        self.score_threshold = score_threshold

    def verify(
        self,
        request: VerificationRequest,
        frame: FramePacket | None,
        context: list[FramePacket] | None = None,
    ) -> VerificationResult:
        started_at = perf_counter()

        # TODO:
        # 1. Replace this call with the real foreign repo's verification API.
        # 2. If the foreign model expects a crop array, use build_frame_input(frame, "roi_array", request.roi_hint).
        raw_output = self.model.score(frame, request=request, context=context or [])
        raw_result = raw_output.get("result", raw_output)

        result = self.build_verification_result(
            raw_result,
            request=request,
            verifier_version=self.version,
            score_threshold=self.score_threshold,
            quality_key="quality",
        )
        result.latency_ms = (perf_counter() - started_at) * 1000.0
        result.metadata = {
            **result.metadata,
            "wrapper": "template_external_verifier_wrapper",
        }
        return result
