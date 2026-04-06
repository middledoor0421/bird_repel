from __future__ import annotations

from contextlib import contextmanager
import inspect
from pathlib import Path
import sys
from time import perf_counter
from typing import Any, Mapping, Sequence

import numpy as np
from PIL import Image

from thesis3.components import Detector, Verifier
from thesis3.core import (
    BBox,
    DetectionCandidate,
    DetectorResult,
    FramePacket,
    VerificationRequest,
    VerificationResult,
)
from thesis3.image_io import crop_array, load_rgb_image, normalized_grayscale_std
from thesis3.plugin_loader import load_symbol


class ExternalAdapterSupport:
    @contextmanager
    def _temporary_sys_path(self, entries: Sequence[str] | None = None):
        if not entries:
            yield
            return

        resolved_entries = [str(Path(entry).resolve()) for entry in entries]
        original = list(sys.path)
        for entry in reversed(resolved_entries):
            if entry not in sys.path:
                sys.path.insert(0, entry)
        try:
            yield
        finally:
            sys.path[:] = original

    def instantiate_external_symbol(
        self,
        target: str,
        init_params: Mapping[str, Any] | None = None,
        sys_path_entries: Sequence[str] | None = None,
    ) -> Any:
        with self._temporary_sys_path(sys_path_entries):
            symbol = load_symbol(target)
            params = dict(init_params or {})
            if inspect.isclass(symbol):
                return symbol(**params)
            if callable(symbol):
                return symbol(**params) if params else symbol
            return symbol

    def resolve_inference_callable(self, model: Any, method_name: str | None = None) -> Any:
        if method_name:
            method = getattr(model, method_name, None)
            if method is None or not callable(method):
                raise AttributeError(f"Model does not expose callable method '{method_name}'.")
            return method
        if callable(model):
            return model
        raise TypeError("Model is not callable and no inference method name was provided.")

    def build_frame_input(self, frame: FramePacket | None, input_mode: str, roi: BBox | None = None) -> Any:
        if input_mode == "frame_packet":
            return frame
        if frame is None:
            return None
        if input_mode == "image_path":
            return frame.image_ref
        if input_mode == "loaded_image":
            return load_rgb_image(frame.image_ref)
        if input_mode == "numpy_rgb":
            return load_rgb_image(frame.image_ref).array
        if input_mode == "numpy_bgr":
            return load_rgb_image(frame.image_ref).array[..., ::-1].copy()
        if input_mode == "roi_array":
            return crop_array(load_rgb_image(frame.image_ref).array, roi)
        if input_mode == "roi_bgr_array":
            return crop_array(load_rgb_image(frame.image_ref).array[..., ::-1].copy(), roi)
        if input_mode == "pil_rgb":
            with Image.open(Path(frame.image_ref)) as image:
                return image.convert("RGB")
        if input_mode == "pil_rgb_roi":
            with Image.open(Path(frame.image_ref)) as image:
                rgb = image.convert("RGB")
                if roi is None:
                    return rgb
                x1 = max(0, int(round(roi.x1)))
                y1 = max(0, int(round(roi.y1)))
                x2 = max(x1 + 1, int(round(roi.x2)))
                y2 = max(y1 + 1, int(round(roi.y2)))
                return rgb.crop((x1, y1, x2, y2))
        raise ValueError(f"Unsupported input_mode: {input_mode}")

    def extract_path(self, payload: Any, path: str | None) -> Any:
        if path is None or path == "":
            return payload
        current = payload
        for segment in path.split("."):
            if isinstance(current, Mapping):
                current = current[segment]
                continue
            if isinstance(current, Sequence) and not isinstance(current, (str, bytes, bytearray)):
                current = current[int(segment)]
                continue
            raise KeyError(f"Unable to traverse segment '{segment}' on value of type {type(current).__name__}.")
        return current

    def coerce_bbox(self, raw_bbox: Any) -> BBox | None:
        if raw_bbox is None:
            return None
        if isinstance(raw_bbox, BBox):
            return raw_bbox
        if isinstance(raw_bbox, Mapping):
            if {"x1", "y1", "x2", "y2"}.issubset(raw_bbox):
                return BBox(
                    x1=float(raw_bbox["x1"]),
                    y1=float(raw_bbox["y1"]),
                    x2=float(raw_bbox["x2"]),
                    y2=float(raw_bbox["y2"]),
                )
            if {"left", "top", "right", "bottom"}.issubset(raw_bbox):
                return BBox(
                    x1=float(raw_bbox["left"]),
                    y1=float(raw_bbox["top"]),
                    x2=float(raw_bbox["right"]),
                    y2=float(raw_bbox["bottom"]),
                )
        if isinstance(raw_bbox, Sequence) and not isinstance(raw_bbox, (str, bytes, bytearray)) and len(raw_bbox) == 4:
            return BBox(
                x1=float(raw_bbox[0]),
                y1=float(raw_bbox[1]),
                x2=float(raw_bbox[2]),
                y2=float(raw_bbox[3]),
            )
        raise TypeError(f"Unsupported bbox value: {raw_bbox!r}")

    def build_detection_candidate(
        self,
        raw: Mapping[str, Any],
        *,
        frame: FramePacket,
        index: int,
        detector_version: str,
        bbox_key: str = "bbox",
        score_key: str = "score",
        class_name_key: str = "class_name",
        candidate_id_key: str = "candidate_id",
        default_class_name: str = "bird",
    ) -> DetectionCandidate:
        score = float(raw.get(score_key, raw.get("confidence", 0.0)))
        bbox = self.coerce_bbox(raw.get(bbox_key))
        return DetectionCandidate(
            candidate_id=str(raw.get(candidate_id_key, f"{frame.frame_id}:external:{index}")),
            frame_id=frame.frame_id,
            camera_id=frame.camera_id,
            bbox=bbox,
            class_name=str(raw.get(class_name_key, default_class_name)),
            detector_confidence=score,
            detector_version=detector_version,
            metadata={
                key: value
                for key, value in raw.items()
                if key not in {bbox_key, score_key, "confidence", class_name_key, candidate_id_key}
            },
        )

    def build_verification_result(
        self,
        raw: Any,
        *,
        request: VerificationRequest,
        verifier_version: str,
        score_threshold: float = 0.5,
        score_key: str = "score",
        verified_key: str = "verified",
        quality_key: str = "quality_score",
        failure_reason_key: str = "failure_reason",
        uncertainty_key: str = "uncertainty",
        supporting_bbox_key: str = "supporting_bbox",
        default_quality: float | None = None,
    ) -> VerificationResult:
        if isinstance(raw, bool):
            score = 1.0 if raw else 0.0
            verified = raw
            quality_score = default_quality
            failure_reason = None if raw else "external_boolean_reject"
            uncertainty = max(0.0, 1.0 - score)
            supporting_bbox = request.roi_hint
            metadata: dict[str, Any] = {}
        elif isinstance(raw, (int, float)):
            score = float(raw)
            verified = score >= score_threshold
            quality_score = default_quality
            failure_reason = None if verified else "score_below_threshold"
            uncertainty = max(0.0, 1.0 - score)
            supporting_bbox = request.roi_hint
            metadata = {}
        elif isinstance(raw, Mapping):
            score = float(raw.get(score_key, raw.get("confidence", 0.0)))
            verified = bool(raw.get(verified_key, score >= score_threshold))
            quality_score = raw.get(quality_key, default_quality)
            quality_score = float(quality_score) if quality_score is not None else None
            failure_reason = raw.get(failure_reason_key)
            uncertainty = raw.get(uncertainty_key)
            uncertainty = float(uncertainty) if uncertainty is not None else max(0.0, 1.0 - score)
            supporting_bbox = self.coerce_bbox(raw.get(supporting_bbox_key, request.roi_hint))
            metadata = {
                key: value
                for key, value in raw.items()
                if key
                not in {
                    score_key,
                    "confidence",
                    verified_key,
                    quality_key,
                    failure_reason_key,
                    uncertainty_key,
                    supporting_bbox_key,
                }
            }
        else:
            raise TypeError(f"Unsupported verification output type: {type(raw).__name__}")

        return VerificationResult(
            request_id=request.request_id,
            verified=verified,
            verifier_score=score,
            verifier_version=verifier_version,
            latency_ms=0.0,
            supporting_bbox=supporting_bbox,
            quality_score=quality_score,
            failure_reason=failure_reason,
            uncertainty=uncertainty,
            metadata=metadata,
        )


class GenericExternalDetector(ExternalAdapterSupport, Detector):
    version = "generic_external_detector_v1"

    def __init__(
        self,
        model_target: str,
        model_init_params: Mapping[str, Any] | None = None,
        predict_method: str | None = "predict",
        input_mode: str = "image_path",
        result_path: str | None = None,
        bbox_key: str = "bbox",
        score_key: str = "score",
        class_name_key: str = "class_name",
        candidate_id_key: str = "candidate_id",
        default_class_name: str = "bird",
        min_confidence: float = 0.0,
        pass_frame: bool = False,
        pass_roi: bool = False,
        sys_path_entries: Sequence[str] | None = None,
    ) -> None:
        self.model_target = model_target
        self.model = self.instantiate_external_symbol(
            model_target,
            model_init_params,
            sys_path_entries=sys_path_entries,
        )
        self.predict_method = predict_method
        self.input_mode = input_mode
        self.result_path = result_path
        self.bbox_key = bbox_key
        self.score_key = score_key
        self.class_name_key = class_name_key
        self.candidate_id_key = candidate_id_key
        self.default_class_name = default_class_name
        self.min_confidence = min_confidence
        self.pass_frame = pass_frame
        self.pass_roi = pass_roi

    def detect(self, frame: FramePacket, roi: BBox | None = None) -> DetectorResult:
        started_at = perf_counter()
        model_input = self.build_frame_input(frame, self.input_mode, roi)
        infer = self.resolve_inference_callable(self.model, self.predict_method)
        kwargs: dict[str, Any] = {}
        if self.pass_frame:
            kwargs["frame"] = frame
        if self.pass_roi:
            kwargs["roi"] = roi
        raw_output = infer(model_input, **kwargs)
        raw_detections = self.extract_path(raw_output, self.result_path)
        if raw_detections is None:
            raw_detections = []
        if not isinstance(raw_detections, Sequence) or isinstance(raw_detections, (str, bytes, bytearray)):
            raise TypeError("GenericExternalDetector expects a sequence of detection mappings.")

        candidates: list[DetectionCandidate] = []
        for index, raw in enumerate(raw_detections):
            if not isinstance(raw, Mapping):
                raise TypeError("Each external detection must be a mapping.")
            candidate = self.build_detection_candidate(
                raw,
                frame=frame,
                index=index,
                detector_version=self.version,
                bbox_key=self.bbox_key,
                score_key=self.score_key,
                class_name_key=self.class_name_key,
                candidate_id_key=self.candidate_id_key,
                default_class_name=self.default_class_name,
            )
            if candidate.detector_confidence >= self.min_confidence:
                candidates.append(candidate)

        return DetectorResult(
            candidates=candidates,
            latency_ms=(perf_counter() - started_at) * 1000.0,
            diagnostics={
                "source": "generic_external_detector",
                "model_target": self.model_target,
                "input_mode": self.input_mode,
                "result_path": self.result_path,
            },
        )


class GenericExternalVerifier(ExternalAdapterSupport, Verifier):
    version = "generic_external_verifier_v1"

    def __init__(
        self,
        model_target: str,
        model_init_params: Mapping[str, Any] | None = None,
        predict_method: str | None = "predict",
        input_mode: str = "image_path",
        result_path: str | None = None,
        score_key: str = "score",
        verified_key: str = "verified",
        quality_key: str = "quality_score",
        failure_reason_key: str = "failure_reason",
        uncertainty_key: str = "uncertainty",
        supporting_bbox_key: str = "supporting_bbox",
        score_threshold: float = 0.5,
        default_quality_from_frame: bool = True,
        pass_request: bool = False,
        pass_frame: bool = False,
        pass_context: bool = False,
        pass_roi: bool = False,
        sys_path_entries: Sequence[str] | None = None,
    ) -> None:
        self.model_target = model_target
        self.model = self.instantiate_external_symbol(
            model_target,
            model_init_params,
            sys_path_entries=sys_path_entries,
        )
        self.predict_method = predict_method
        self.input_mode = input_mode
        self.result_path = result_path
        self.score_key = score_key
        self.verified_key = verified_key
        self.quality_key = quality_key
        self.failure_reason_key = failure_reason_key
        self.uncertainty_key = uncertainty_key
        self.supporting_bbox_key = supporting_bbox_key
        self.score_threshold = score_threshold
        self.default_quality_from_frame = default_quality_from_frame
        self.pass_request = pass_request
        self.pass_frame = pass_frame
        self.pass_context = pass_context
        self.pass_roi = pass_roi

    def verify(
        self,
        request: VerificationRequest,
        frame: FramePacket | None,
        context: list[FramePacket] | None = None,
    ) -> VerificationResult:
        started_at = perf_counter()
        model_input = self.build_frame_input(frame, self.input_mode, request.roi_hint)
        infer = self.resolve_inference_callable(self.model, self.predict_method)
        kwargs: dict[str, Any] = {}
        if self.pass_request:
            kwargs["request"] = request
        if self.pass_frame:
            kwargs["frame"] = frame
        if self.pass_context:
            kwargs["context"] = context or []
        if self.pass_roi:
            kwargs["roi"] = request.roi_hint
        raw_output = infer(model_input, **kwargs)
        parsed_output = self.extract_path(raw_output, self.result_path)

        default_quality = None
        if self.default_quality_from_frame and frame is not None:
            default_quality = frame.metadata.get("quality_score")
            if default_quality is None and self.input_mode in {"numpy_rgb", "roi_array"} and isinstance(model_input, np.ndarray):
                default_quality = normalized_grayscale_std(model_input)

        result = self.build_verification_result(
            parsed_output,
            request=request,
            verifier_version=self.version,
            score_threshold=self.score_threshold,
            score_key=self.score_key,
            verified_key=self.verified_key,
            quality_key=self.quality_key,
            failure_reason_key=self.failure_reason_key,
            uncertainty_key=self.uncertainty_key,
            supporting_bbox_key=self.supporting_bbox_key,
            default_quality=float(default_quality) if default_quality is not None else None,
        )
        result.latency_ms = (perf_counter() - started_at) * 1000.0
        result.metadata = {
            **result.metadata,
            "context_frames": len(context or []),
            "model_target": self.model_target,
        }
        return result
