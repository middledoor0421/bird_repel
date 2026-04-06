from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import replace
from time import perf_counter
from typing import Any

import numpy as np

from thesis3.core import (
    BBox,
    DetectionCandidate,
    DetectorResult,
    FactoryRegistry,
    FramePacket,
    TrackLifecycleState,
    TrackState,
    TrackerUpdate,
    VerificationRequest,
    VerificationResult,
)
from thesis3.image_io import (
    bbox_iou,
    centered_bbox,
    crop_array,
    load_rgb_image,
    normalized_grayscale_mean,
    normalized_grayscale_std,
)


class Detector(ABC):
    version: str

    @abstractmethod
    def detect(self, frame: FramePacket, roi: BBox | None = None) -> DetectorResult:
        raise NotImplementedError


class Verifier(ABC):
    version: str

    @abstractmethod
    def verify(
        self,
        request: VerificationRequest,
        frame: FramePacket | None,
        context: list[FramePacket] | None = None,
    ) -> VerificationResult:
        raise NotImplementedError


class Tracker(ABC):
    version: str

    @abstractmethod
    def update(self, candidates: list[DetectionCandidate], frame: FramePacket) -> TrackerUpdate:
        raise NotImplementedError


class ManifestDetector(Detector):
    version = "manifest_detector_v1"

    def __init__(self, min_confidence: float = 0.0) -> None:
        self.min_confidence = min_confidence

    def detect(self, frame: FramePacket, roi: BBox | None = None) -> DetectorResult:
        candidates: list[DetectionCandidate] = []
        for index, raw in enumerate(frame.metadata.get("detections", [])):
            score = float(raw.get("score", raw.get("detector_confidence", 0.0)))
            if score < self.min_confidence:
                continue
            bbox_raw = raw.get("bbox")
            bbox = BBox(*bbox_raw) if bbox_raw is not None else None
            metadata = {key: value for key, value in raw.items() if key not in {"bbox", "score"}}
            candidate = DetectionCandidate(
                candidate_id=str(raw.get("candidate_id", f"{frame.frame_id}:cand:{index}")),
                frame_id=frame.frame_id,
                camera_id=frame.camera_id,
                bbox=bbox,
                class_name=str(raw.get("class_name", "unknown")),
                detector_confidence=score,
                detector_version=self.version,
                metadata=metadata,
            )
            candidates.append(candidate)
        latency_ms = float(frame.metadata.get("detector_latency_ms", 0.0))
        return DetectorResult(candidates=candidates, latency_ms=latency_ms, diagnostics={"source": "manifest"})


class GTMetadataDetector(Detector):
    version = "gt_metadata_detector_v1"

    def __init__(
        self,
        min_confidence: float = 0.0,
        default_score: float = 0.99,
        class_name_filter: str | None = None,
    ) -> None:
        self.min_confidence = min_confidence
        self.default_score = default_score
        self.class_name_filter = class_name_filter

    def detect(self, frame: FramePacket, roi: BBox | None = None) -> DetectorResult:
        started_at = perf_counter()
        image = load_rgb_image(frame.image_ref)
        candidates: list[DetectionCandidate] = []
        for index, raw in enumerate(frame.metadata.get("gt_objects", [])):
            class_name = str(raw.get("class_name", "bird"))
            if self.class_name_filter is not None and class_name != self.class_name_filter:
                continue
            bbox_raw = raw.get("bbox")
            if bbox_raw is None:
                continue
            bbox = BBox(*bbox_raw)
            score = float(raw.get("score", self.default_score))
            if score < self.min_confidence:
                continue
            metadata = {key: value for key, value in raw.items() if key not in {"bbox", "score"}}
            candidates.append(
                DetectionCandidate(
                    candidate_id=str(raw.get("object_id", f"{frame.frame_id}:gt:{index}")),
                    frame_id=frame.frame_id,
                    camera_id=frame.camera_id,
                    bbox=bbox,
                    class_name=class_name,
                    detector_confidence=score,
                    detector_version=self.version,
                    metadata=metadata,
                )
            )

        latency_ms = (perf_counter() - started_at) * 1000.0
        diagnostics = {
            "source": "gt_metadata",
            "image_width": image.width,
            "image_height": image.height,
        }
        return DetectorResult(candidates=candidates, latency_ms=latency_ms, diagnostics=diagnostics)


class MeanIntensityDetector(Detector):
    version = "mean_intensity_detector_v1"

    def __init__(
        self,
        min_mean_intensity: float = 0.2,
        bbox_width_ratio: float = 0.2,
        bbox_height_ratio: float = 0.2,
        class_name: str = "target",
        score_bias: float = 0.0,
    ) -> None:
        self.min_mean_intensity = min_mean_intensity
        self.bbox_width_ratio = bbox_width_ratio
        self.bbox_height_ratio = bbox_height_ratio
        self.class_name = class_name
        self.score_bias = score_bias

    def detect(self, frame: FramePacket, roi: BBox | None = None) -> DetectorResult:
        started_at = perf_counter()
        image = load_rgb_image(frame.image_ref)
        mean_intensity = normalized_grayscale_mean(image.array)
        candidates: list[DetectionCandidate] = []
        if mean_intensity >= self.min_mean_intensity:
            bbox = centered_bbox(
                width=image.width,
                height=image.height,
                width_ratio=self.bbox_width_ratio,
                height_ratio=self.bbox_height_ratio,
            )
            score = float(min(1.0, self.score_bias + mean_intensity))
            candidates.append(
                DetectionCandidate(
                    candidate_id=f"{frame.frame_id}:intensity",
                    frame_id=frame.frame_id,
                    camera_id=frame.camera_id,
                    bbox=bbox,
                    class_name=self.class_name,
                    detector_confidence=score,
                    detector_version=self.version,
                    metadata={"mean_intensity": mean_intensity},
                )
            )

        latency_ms = (perf_counter() - started_at) * 1000.0
        return DetectorResult(
            candidates=candidates,
            latency_ms=latency_ms,
            diagnostics={"source": "image_mean_intensity", "mean_intensity": mean_intensity},
        )


class HeuristicVerifier(Verifier):
    version = "heuristic_verifier_v1"

    def __init__(
        self,
        score_threshold: float = 0.7,
        min_quality: float = 0.3,
        candidate_weight: float = 0.6,
    ) -> None:
        self.score_threshold = score_threshold
        self.min_quality = min_quality
        self.candidate_weight = candidate_weight

    def verify(
        self,
        request: VerificationRequest,
        frame: FramePacket | None,
        context: list[FramePacket] | None = None,
    ) -> VerificationResult:
        quality_score = 1.0
        if frame is not None:
            quality_score = float(frame.metadata.get("quality_score", 1.0))

        explicit_score = None
        if frame is not None:
            explicit_score = frame.metadata.get("verification_score")

        candidate_confidence = float(request.metadata.get("candidate_confidence", 0.0))
        verifier_score = (
            float(explicit_score)
            if explicit_score is not None
            else (candidate_confidence * self.candidate_weight) + (quality_score * (1.0 - self.candidate_weight))
        )

        verified = verifier_score >= self.score_threshold and quality_score >= self.min_quality
        if quality_score < self.min_quality:
            failure_reason = "quality_below_threshold"
        elif verified:
            failure_reason = None
        else:
            failure_reason = "score_below_threshold"

        return VerificationResult(
            request_id=request.request_id,
            verified=verified,
            verifier_score=verifier_score,
            verifier_version=self.version,
            latency_ms=float(frame.metadata.get("verification_latency_ms", 0.0)) if frame is not None else 0.0,
            supporting_bbox=request.roi_hint,
            quality_score=quality_score,
            failure_reason=failure_reason,
            uncertainty=max(0.0, 1.0 - verifier_score),
            metadata={"context_frames": len(context or [])},
        )


class GTMetadataVerifier(Verifier):
    version = "gt_metadata_verifier_v1"

    def __init__(
        self,
        min_iou: float = 0.1,
        require_same_class: bool = False,
        default_quality: float = 1.0,
    ) -> None:
        self.min_iou = min_iou
        self.require_same_class = require_same_class
        self.default_quality = default_quality

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
                failure_reason="missing_frame",
                quality_score=0.0,
                uncertainty=1.0,
                metadata={"context_frames": len(context or [])},
            )

        image = load_rgb_image(frame.image_ref)
        gt_objects = frame.metadata.get("gt_objects", [])
        requested_class = request.metadata.get("class_name")
        best_iou = 0.0
        matched_object_id: str | None = None

        for raw in gt_objects:
            bbox_raw = raw.get("bbox")
            if bbox_raw is None:
                continue
            if self.require_same_class and requested_class is not None:
                if raw.get("class_name") != requested_class:
                    continue
            gt_bbox = BBox(*bbox_raw)
            candidate_iou = 1.0 if request.roi_hint is None else bbox_iou(request.roi_hint, gt_bbox)
            if candidate_iou > best_iou:
                best_iou = candidate_iou
                matched_object_id = raw.get("object_id")

        quality_score = float(frame.metadata.get("quality_score", normalized_grayscale_std(image.array) or self.default_quality))
        verified = best_iou >= self.min_iou if request.roi_hint is not None else bool(gt_objects)
        failure_reason = None if verified else "no_matching_gt"
        latency_ms = (perf_counter() - started_at) * 1000.0
        return VerificationResult(
            request_id=request.request_id,
            verified=verified,
            verifier_score=best_iou if request.roi_hint is not None else float(bool(gt_objects)),
            verifier_version=self.version,
            latency_ms=latency_ms,
            supporting_bbox=request.roi_hint,
            quality_score=quality_score,
            failure_reason=failure_reason,
            uncertainty=max(0.0, 1.0 - best_iou),
            metadata={
                "context_frames": len(context or []),
                "matched_object_id": matched_object_id,
                "gt_count": len(gt_objects),
            },
        )


class CropVarianceVerifier(Verifier):
    version = "crop_variance_verifier_v1"

    def __init__(self, min_variance_score: float = 0.15) -> None:
        self.min_variance_score = min_variance_score

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
                quality_score=0.0,
                failure_reason="missing_frame",
                uncertainty=1.0,
                metadata={"context_frames": len(context or [])},
            )

        image = load_rgb_image(frame.image_ref)
        patch = crop_array(image.array, request.roi_hint)
        if patch.size == 0:
            variance_score = 0.0
            quality_score = 0.0
            verified = False
            failure_reason = "empty_roi"
        else:
            grayscale = patch.mean(axis=2) if patch.ndim == 3 else patch
            variance_score = float(min(1.0, np.asarray(grayscale, dtype=np.float32).std() / 64.0))
            quality_score = float(frame.metadata.get("quality_score", normalized_grayscale_std(patch)))
            verified = variance_score >= self.min_variance_score
            failure_reason = None if verified else "variance_below_threshold"

        latency_ms = (perf_counter() - started_at) * 1000.0
        return VerificationResult(
            request_id=request.request_id,
            verified=verified,
            verifier_score=variance_score,
            verifier_version=self.version,
            latency_ms=latency_ms,
            supporting_bbox=request.roi_hint,
            quality_score=quality_score,
            failure_reason=failure_reason,
            uncertainty=max(0.0, 1.0 - variance_score),
            metadata={"context_frames": len(context or [])},
        )


class SimpleTracker(Tracker):
    version = "simple_tracker_v1"

    def __init__(self, confirm_after: int = 2, max_missing_seconds: float = 0.5) -> None:
        self.confirm_after = max(1, confirm_after)
        self.max_missing_seconds = max_missing_seconds
        self._tracks_by_key: dict[str, TrackState] = {}
        self._track_counter = 0

    def update(self, candidates: list[DetectionCandidate], frame: FramePacket) -> TrackerUpdate:
        started_at = perf_counter()
        current_keys: set[str] = set()
        association: dict[str, str] = {}
        new_tracks: list[str] = []
        active_tracks: list[TrackState] = []

        for candidate in candidates:
            key = str(candidate.metadata.get("object_id", candidate.candidate_id))
            current_keys.add(key)
            track = self._tracks_by_key.get(key)
            if track is None:
                self._track_counter += 1
                track = TrackState(
                    track_id=f"trk-{self._track_counter:04d}",
                    candidate_ids=[candidate.candidate_id],
                    start_time=frame.timestamp,
                    last_seen_time=frame.timestamp,
                    camera_history=[frame.camera_id],
                    state=TrackLifecycleState.NEW,
                    track_confidence=candidate.detector_confidence,
                    metadata={"object_key": key},
                )
                new_tracks.append(track.track_id)
            else:
                track = replace(
                    track,
                    candidate_ids=[*track.candidate_ids, candidate.candidate_id],
                    last_seen_time=frame.timestamp,
                    camera_history=[*track.camera_history, frame.camera_id],
                    track_confidence=max(track.track_confidence, candidate.detector_confidence),
                )

            if len(track.candidate_ids) >= self.confirm_after:
                track = replace(track, state=TrackLifecycleState.CONFIRMED)
            elif len(track.candidate_ids) > 1:
                track = replace(track, state=TrackLifecycleState.TENTATIVE)

            self._tracks_by_key[key] = track
            association[candidate.candidate_id] = track.track_id
            active_tracks.append(track)

        lost_tracks: list[str] = []
        for key, track in list(self._tracks_by_key.items()):
            if key in current_keys:
                continue
            if frame.timestamp - track.last_seen_time > self.max_missing_seconds:
                self._tracks_by_key[key] = replace(track, state=TrackLifecycleState.LOST)
                lost_tracks.append(track.track_id)

        return TrackerUpdate(
            tracks=active_tracks,
            association=association,
            lost_tracks=lost_tracks,
            new_tracks=new_tracks,
            latency_ms=(perf_counter() - started_at) * 1000.0,
        )


def build_default_registries() -> tuple[FactoryRegistry, FactoryRegistry, FactoryRegistry]:
    from thesis3.external_adapters import GenericExternalDetector, GenericExternalVerifier
    from thesis3.research_repo_adapters import (
        BirdRepelDetectorWrapper,
        BirdSahiTemporalLocalVerifier,
        BirdSahiTemporalYoloWrapper,
    )

    detector_registry = FactoryRegistry()
    detector_registry.register(
        "manifest_detector",
        lambda params: ManifestDetector(min_confidence=float(params.get("min_confidence", 0.0))),
    )
    detector_registry.register(
        "gt_metadata_detector",
        lambda params: GTMetadataDetector(
            min_confidence=float(params.get("min_confidence", 0.0)),
            default_score=float(params.get("default_score", 0.99)),
            class_name_filter=params.get("class_name_filter"),
        ),
    )
    detector_registry.register(
        "mean_intensity_detector",
        lambda params: MeanIntensityDetector(
            min_mean_intensity=float(params.get("min_mean_intensity", 0.2)),
            bbox_width_ratio=float(params.get("bbox_width_ratio", 0.2)),
            bbox_height_ratio=float(params.get("bbox_height_ratio", 0.2)),
            class_name=str(params.get("class_name", "target")),
            score_bias=float(params.get("score_bias", 0.0)),
        ),
    )
    detector_registry.register(
        "generic_external_detector",
        lambda params: GenericExternalDetector(
            model_target=str(params["model_target"]),
            model_init_params=params.get("model_init_params"),
            predict_method=params.get("predict_method", "predict"),
            input_mode=str(params.get("input_mode", "image_path")),
            result_path=params.get("result_path"),
            bbox_key=str(params.get("bbox_key", "bbox")),
            score_key=str(params.get("score_key", "score")),
            class_name_key=str(params.get("class_name_key", "class_name")),
            candidate_id_key=str(params.get("candidate_id_key", "candidate_id")),
            default_class_name=str(params.get("default_class_name", "bird")),
            min_confidence=float(params.get("min_confidence", 0.0)),
            pass_frame=bool(params.get("pass_frame", False)),
            pass_roi=bool(params.get("pass_roi", False)),
            sys_path_entries=params.get("sys_path_entries"),
        ),
    )
    detector_registry.register(
        "bird_repel_detector",
        lambda params: BirdRepelDetectorWrapper(
            model_target=str(params.get("model_target", "../bird_repel/central/detector/model.py:BirdDetector")),
            model_init_params=params.get("model_init_params"),
            input_mode=str(params.get("input_mode", "numpy_bgr")),
            class_name=str(params.get("class_name", "bird")),
            min_confidence=float(params.get("min_confidence", 0.0)),
            sys_path_entries=params.get("sys_path_entries"),
        ),
    )
    detector_registry.register(
        "bird_sahi_temporal_yolo_detector",
        lambda params: BirdSahiTemporalYoloWrapper(
            model_target=str(
                params.get("model_target", "../bird_sahi_temporal/detector/yolo_wrapper.py:YoloDetector")
            ),
            model_init_params=params.get("model_init_params"),
            input_mode=str(params.get("input_mode", "numpy_rgb")),
            class_mapping_path=params.get("class_mapping_path"),
            class_name_map=params.get("class_name_map"),
            default_class_name=str(params.get("default_class_name", "bird")),
            min_confidence=float(params.get("min_confidence", 0.0)),
            predict_conf_thres=float(params["predict_conf_thres"]) if params.get("predict_conf_thres") is not None else None,
            predict_img_size=int(params["predict_img_size"]) if params.get("predict_img_size") is not None else None,
            sys_path_entries=params.get("sys_path_entries"),
        ),
    )

    verifier_registry = FactoryRegistry()
    verifier_registry.register(
        "heuristic_verifier",
        lambda params: HeuristicVerifier(
            score_threshold=float(params.get("score_threshold", 0.7)),
            min_quality=float(params.get("min_quality", 0.3)),
            candidate_weight=float(params.get("candidate_weight", 0.6)),
        ),
    )
    verifier_registry.register(
        "gt_metadata_verifier",
        lambda params: GTMetadataVerifier(
            min_iou=float(params.get("min_iou", 0.1)),
            require_same_class=bool(params.get("require_same_class", False)),
            default_quality=float(params.get("default_quality", 1.0)),
        ),
    )
    verifier_registry.register(
        "crop_variance_verifier",
        lambda params: CropVarianceVerifier(
            min_variance_score=float(params.get("min_variance_score", 0.15)),
        ),
    )
    verifier_registry.register(
        "generic_external_verifier",
        lambda params: GenericExternalVerifier(
            model_target=str(params["model_target"]),
            model_init_params=params.get("model_init_params"),
            predict_method=params.get("predict_method", "predict"),
            input_mode=str(params.get("input_mode", "image_path")),
            result_path=params.get("result_path"),
            score_key=str(params.get("score_key", "score")),
            verified_key=str(params.get("verified_key", "verified")),
            quality_key=str(params.get("quality_key", "quality_score")),
            failure_reason_key=str(params.get("failure_reason_key", "failure_reason")),
            uncertainty_key=str(params.get("uncertainty_key", "uncertainty")),
            supporting_bbox_key=str(params.get("supporting_bbox_key", "supporting_bbox")),
            score_threshold=float(params.get("score_threshold", 0.5)),
            default_quality_from_frame=bool(params.get("default_quality_from_frame", True)),
            pass_request=bool(params.get("pass_request", False)),
            pass_frame=bool(params.get("pass_frame", False)),
            pass_context=bool(params.get("pass_context", False)),
            pass_roi=bool(params.get("pass_roi", False)),
            sys_path_entries=params.get("sys_path_entries"),
        ),
    )
    verifier_registry.register(
        "bird_sahi_temporal_local_verifier",
        lambda params: BirdSahiTemporalLocalVerifier(
            model_target=str(
                params.get("model_target", "../bird_sahi_temporal/detector/yolo_wrapper.py:YoloDetector")
            ),
            model_init_params=params.get("model_init_params"),
            input_mode=str(params.get("input_mode", "roi_array")),
            class_mapping_path=params.get("class_mapping_path"),
            class_name_map=params.get("class_name_map"),
            target_labels=params.get("target_labels"),
            score_threshold=float(params.get("score_threshold", 0.7)),
            min_quality=float(params.get("min_quality", 0.0)),
            predict_conf_thres=float(params["predict_conf_thres"]) if params.get("predict_conf_thres") is not None else None,
            predict_img_size=int(params["predict_img_size"]) if params.get("predict_img_size") is not None else None,
            sys_path_entries=params.get("sys_path_entries"),
        ),
    )

    tracker_registry = FactoryRegistry()
    tracker_registry.register(
        "simple_tracker",
        lambda params: SimpleTracker(
            confirm_after=int(params.get("confirm_after", 2)),
            max_missing_seconds=float(params.get("max_missing_seconds", 0.5)),
        ),
    )
    return detector_registry, verifier_registry, tracker_registry
