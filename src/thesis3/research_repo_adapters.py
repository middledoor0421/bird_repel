from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from thesis3.components import Detector, Verifier
from thesis3.core import (
    BBox,
    DetectionCandidate,
    DetectorResult,
    FramePacket,
    VerificationRequest,
    VerificationResult,
)
from thesis3.external_adapters import ExternalAdapterSupport


def _load_int_mapping(path: str | None) -> dict[int, int] | None:
    if path is None:
        return None
    mapping_path = Path(path)
    if not mapping_path.exists():
        raise FileNotFoundError(f"Mapping file not found: {mapping_path}")
    raw = json.loads(mapping_path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise TypeError(f"Expected mapping json at {mapping_path}")
    return {int(key): int(value) for key, value in raw.items()}


class BirdRepelDetectorWrapper(ExternalAdapterSupport, Detector):
    version = "bird_repel_detector_wrapper_v1"

    def __init__(
        self,
        model_target: str = "../bird_repel/central/detector/model.py:BirdDetector",
        model_init_params: Mapping[str, Any] | None = None,
        input_mode: str = "numpy_bgr",
        class_name: str = "bird",
        min_confidence: float = 0.0,
        sys_path_entries: Sequence[str] | None = None,
    ) -> None:
        self.model_target = model_target
        self.model = self.instantiate_external_symbol(
            model_target,
            model_init_params,
            sys_path_entries=sys_path_entries,
        )
        self.input_mode = input_mode
        self.class_name = class_name
        self.min_confidence = min_confidence

    def detect(self, frame: FramePacket, roi: BBox | None = None) -> DetectorResult:
        started_at = perf_counter()
        model_input = self.build_frame_input(frame, self.input_mode, roi)
        raw_detections = self.model.infer(model_input)
        candidates: list[DetectionCandidate] = []

        for index, raw in enumerate(raw_detections or []):
            box = getattr(raw, "box", None)
            conf = getattr(raw, "conf", None)
            if isinstance(raw, Mapping):
                box = raw.get("box", box)
                conf = raw.get("conf", conf)
            if box is None or conf is None:
                continue
            x, y, w, h = [float(value) for value in box]
            score = float(conf)
            if score < self.min_confidence:
                continue
            bbox = BBox(x1=x, y1=y, x2=x + w, y2=y + h)
            candidates.append(
                DetectionCandidate(
                    candidate_id=f"{frame.frame_id}:bird_repel:{index}",
                    frame_id=frame.frame_id,
                    camera_id=frame.camera_id,
                    bbox=bbox,
                    class_name=self.class_name,
                    detector_confidence=score,
                    detector_version=self.version,
                    metadata={"source_wrapper": "bird_repel", "model_target": self.model_target},
                )
            )

        return DetectorResult(
            candidates=candidates,
            latency_ms=(perf_counter() - started_at) * 1000.0,
            diagnostics={"source": "bird_repel_detector_wrapper", "input_mode": self.input_mode},
        )


class BirdSahiTemporalYoloWrapper(ExternalAdapterSupport, Detector):
    version = "bird_sahi_temporal_yolo_wrapper_v1"

    def __init__(
        self,
        model_target: str = "../bird_sahi_temporal/detector/yolo_wrapper.py:YoloDetector",
        model_init_params: Mapping[str, Any] | None = None,
        input_mode: str = "numpy_rgb",
        class_mapping_path: str | None = None,
        class_name_map: Mapping[str, str] | Mapping[int, str] | None = None,
        default_class_name: str = "bird",
        min_confidence: float = 0.0,
        predict_conf_thres: float | None = None,
        predict_img_size: int | None = None,
        sys_path_entries: Sequence[str] | None = None,
    ) -> None:
        self.model_target = model_target
        init_params = dict(model_init_params or {})
        class_mapping = _load_int_mapping(class_mapping_path)
        if class_mapping is not None and "class_mapping" not in init_params:
            init_params["class_mapping"] = class_mapping
        self._model_init_params = init_params
        self.input_mode = input_mode
        self.default_class_name = default_class_name
        self.min_confidence = min_confidence
        self.predict_conf_thres = predict_conf_thres
        self.predict_img_size = predict_img_size
        self.sys_path_entries = sys_path_entries
        self._model: Any | None = None
        normalized_map: dict[int, str] = {}
        for key, value in (class_name_map or {}).items():
            normalized_map[int(key)] = str(value)
        self.class_name_map = normalized_map

    def _ensure_model(self) -> Any:
        if self._model is None:
            self._model = self.instantiate_external_symbol(
                self.model_target,
                self._model_init_params,
                sys_path_entries=self.sys_path_entries,
            )
        return self._model

    def detect(self, frame: FramePacket, roi: BBox | None = None) -> DetectorResult:
        started_at = perf_counter()
        model_input = self.build_frame_input(frame, self.input_mode, roi)
        model = self._ensure_model()
        boxes, scores, labels = model.predict(
            model_input,
            conf_thres=self.predict_conf_thres,
            img_size=self.predict_img_size,
        )
        boxes_np = np.asarray(boxes, dtype=np.float32)
        scores_np = np.asarray(scores, dtype=np.float32)
        labels_np = np.asarray(labels, dtype=np.int64)

        candidates: list[DetectionCandidate] = []
        for index in range(len(scores_np)):
            score = float(scores_np[index])
            if score < self.min_confidence:
                continue
            x1, y1, x2, y2 = [float(value) for value in boxes_np[index].tolist()]
            label_id = int(labels_np[index]) if len(labels_np) > index else -1
            class_name = self.class_name_map.get(label_id, self.default_class_name)
            candidates.append(
                DetectionCandidate(
                    candidate_id=f"{frame.frame_id}:bird_sahi:{index}",
                    frame_id=frame.frame_id,
                    camera_id=frame.camera_id,
                    bbox=BBox(x1=x1, y1=y1, x2=x2, y2=y2),
                    class_name=class_name,
                    detector_confidence=score,
                    detector_version=self.version,
                    metadata={
                        "source_wrapper": "bird_sahi_temporal",
                        "model_target": self.model_target,
                        "raw_label_id": label_id,
                    },
                )
            )

        return DetectorResult(
            candidates=candidates,
            latency_ms=(perf_counter() - started_at) * 1000.0,
            diagnostics={"source": "bird_sahi_temporal_yolo_wrapper", "input_mode": self.input_mode},
        )


class BirdSahiTemporalLocalVerifier(ExternalAdapterSupport, Verifier):
    version = "bird_sahi_temporal_local_verifier_v1"

    def __init__(
        self,
        model_target: str = "../bird_sahi_temporal/detector/yolo_wrapper.py:YoloDetector",
        model_init_params: Mapping[str, Any] | None = None,
        input_mode: str = "roi_array",
        class_mapping_path: str | None = None,
        class_name_map: Mapping[str, str] | Mapping[int, str] | None = None,
        target_labels: Sequence[str] | None = None,
        score_threshold: float = 0.7,
        min_quality: float = 0.0,
        predict_conf_thres: float | None = None,
        predict_img_size: int | None = None,
        sys_path_entries: Sequence[str] | None = None,
    ) -> None:
        self.model_target = model_target
        init_params = dict(model_init_params or {})
        class_mapping = _load_int_mapping(class_mapping_path)
        if class_mapping is not None and "class_mapping" not in init_params:
            init_params["class_mapping"] = class_mapping
        self._model_init_params = init_params
        self.input_mode = input_mode
        self.score_threshold = float(score_threshold)
        self.min_quality = float(min_quality)
        self.predict_conf_thres = predict_conf_thres
        self.predict_img_size = predict_img_size
        self.sys_path_entries = sys_path_entries
        self._model: Any | None = None
        self.target_labels = {label.lower() for label in (target_labels or ["target", "bird"])}
        normalized_map: dict[int, str] = {}
        for key, value in (class_name_map or {}).items():
            normalized_map[int(key)] = str(value)
        self.class_name_map = normalized_map

    def _ensure_model(self) -> Any:
        if self._model is None:
            self._model = self.instantiate_external_symbol(
                self.model_target,
                self._model_init_params,
                sys_path_entries=self.sys_path_entries,
            )
        return self._model

    def verify(
        self,
        request: VerificationRequest,
        frame: FramePacket | None,
        context: list[FramePacket] | None = None,
    ) -> VerificationResult:
        started_at = perf_counter()
        if frame is None:
            return VerificationResult(
                request_id=request.request_id,
                verified=False,
                verifier_score=0.0,
                verifier_version=self.version,
                latency_ms=(perf_counter() - started_at) * 1000.0,
                supporting_bbox=request.roi_hint,
                quality_score=None,
                failure_reason="verification_frame_missing",
                uncertainty=1.0,
                metadata={"source_wrapper": "bird_sahi_temporal_local_verifier"},
            )

        try:
            model_input = self.build_frame_input(frame, self.input_mode, request.roi_hint)
            if isinstance(model_input, np.ndarray) and model_input.size == 0:
                return VerificationResult(
                    request_id=request.request_id,
                    verified=False,
                    verifier_score=0.0,
                    verifier_version=self.version,
                    latency_ms=(perf_counter() - started_at) * 1000.0,
                    supporting_bbox=request.roi_hint,
                    quality_score=float(frame.metadata.get("quality_score", 1.0)),
                    failure_reason="empty_roi_crop",
                    uncertainty=1.0,
                    metadata={"source_wrapper": "bird_sahi_temporal_local_verifier"},
                )

            model = self._ensure_model()
            boxes, scores, labels = model.predict(
                model_input,
                conf_thres=self.predict_conf_thres,
                img_size=self.predict_img_size,
            )
        except FileNotFoundError:
            fallback_score = frame.metadata.get("verification_score")
            if fallback_score is None:
                raise
            best_score = float(fallback_score)
            quality_score = float(frame.metadata.get("quality_score", 1.0))
            verified = bool(best_score >= self.score_threshold and quality_score >= self.min_quality)
            return VerificationResult(
                request_id=request.request_id,
                verified=verified,
                verifier_score=best_score,
                verifier_version=self.version,
                latency_ms=(perf_counter() - started_at) * 1000.0,
                supporting_bbox=request.roi_hint,
                quality_score=quality_score,
                failure_reason=None if verified else "metadata_fallback_score_below_threshold",
                uncertainty=max(0.0, 1.0 - best_score),
                metadata={
                    "source_wrapper": "bird_sahi_temporal_local_verifier",
                    "fallback_source": "frame.metadata.verification_score",
                },
            )
        scores_np = np.asarray(scores, dtype=np.float32)
        labels_np = np.asarray(labels, dtype=np.int64)

        best_score = 0.0
        matched_labels: list[str] = []
        for index in range(len(scores_np)):
            label_id = int(labels_np[index]) if len(labels_np) > index else -1
            class_name = self.class_name_map.get(label_id, str(label_id))
            if class_name.lower() not in self.target_labels:
                continue
            matched_labels.append(class_name)
            best_score = max(best_score, float(scores_np[index]))

        quality_score = float(frame.metadata.get("quality_score", 1.0))
        verified = bool(best_score >= self.score_threshold and quality_score >= self.min_quality)
        if quality_score < self.min_quality:
            failure_reason = "quality_below_threshold"
        elif verified:
            failure_reason = None
        elif best_score <= 0.0:
            failure_reason = "local_verifier_no_target_detection"
        else:
            failure_reason = "local_verifier_score_below_threshold"

        return VerificationResult(
            request_id=request.request_id,
            verified=verified,
            verifier_score=float(best_score),
            verifier_version=self.version,
            latency_ms=(perf_counter() - started_at) * 1000.0,
            supporting_bbox=request.roi_hint,
            quality_score=quality_score,
            failure_reason=failure_reason,
            uncertainty=max(0.0, 1.0 - float(best_score)),
            metadata={
                "source_wrapper": "bird_sahi_temporal_local_verifier",
                "model_target": self.model_target,
                "matched_labels": matched_labels,
                "raw_detection_count": int(len(scores_np)),
            },
        )
