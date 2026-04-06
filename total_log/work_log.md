# work_log

## 2026-04-05

### GitHub 업로드 준비

- 저장소가 아직 git repo가 아니어서, GitHub 업로드 전에 필요한 기본 준비를 먼저 정리
- 생성물과 캐시를 제외하기 위한 `.gitignore`를 추가하고, 저장소 목적과 디렉터리 구조를 설명하는 `README.md`를 추가
- 기준은 `코드 / 설정 / 메모 / 로그 문서` 중심으로 버전 관리하고, `artifacts/`는 재생성 가능한 실행 결과로 분리하는 것으로 잡음

### 실데이터 수령 전 준비 단계 정리 및 대기 전환

- 지금까지 구현한 modular pipeline, MP4/annotation/GT workflow, GT evaluators, suite/report, audit/stress/camera inventory 준비 상태를 기준으로 사전 준비 단계를 일단 마감
- 현재는 추가 구현을 계속 밀기보다 `실제 데이터`, `camera/site metadata`, `현장 운영 규칙` 도착을 기다리는 대기 상태로 전환
- 다음 재개 시 우선순위는 `실데이터 schema 확정 -> 첫 data audit -> GT 작성 시작 -> baseline / bird-sahi 비교 replay` 순서로 진행

메모:
- 지금 시점의 판단은 "실데이터 전 준비는 충분히 진행됨"이다.
- 이후 변경은 실제 입력 형식과 현장 제약을 본 뒤 조정하는 쪽이 더 효율적이다.

### tracking / handoff GT evaluation 및 markdown report 추가

- `src/thesis3/tracking_gt_evaluation.py`와 `apps/evaluate_tracking_gt.py`를 추가해서 `tracker_update` 로그를 frame annotation의 `object_id` GT와 직접 비교할 수 있게 정리
- continuity recall, object fragmentation, id switch, handoff transition, handoff success / failure를 계산하도록 했고 synthetic multi-camera fixture `examples/tracker_handoff_event_log.example.jsonl`, `examples/tracking_frame_annotations_handoff.example.jsonl`도 같이 추가
- `src/thesis3/gt_eval_report.py`와 `apps/render_gt_eval_report.py`를 추가해서 GT eval suite JSON을 markdown report로 바로 변환할 수 있게 함
- `src/thesis3/gt_eval_suite.py`도 tracking summary까지 matrix에 넣도록 확장해서 event / frame / verification / tracking을 한 report 체계 안에서 볼 수 있게 정리
- smoke 기준 synthetic handoff fixture에서는 handoff transition 2건 중 1건 성공, 1건 실패와 id switch 1건이 정상 집계됨

검증:
- `python -m compileall src apps`
- `python apps/evaluate_tracking_gt.py --event-log examples/tracker_handoff_event_log.example.jsonl --frames examples/tracking_frame_annotations_handoff.example.jsonl --output artifacts/evaluation/example_tracking_eval.json`
- `python apps/run_gt_eval_suite.py --entry handoff=examples/tracker_handoff_event_log.example.jsonl --tracking-frames examples/tracking_frame_annotations_handoff.example.jsonl --output artifacts/evaluation/example_tracking_gt_eval_suite.json`
- `python apps/render_gt_eval_report.py --suite-json artifacts/evaluation/example_gt_eval_suite_with_verification.json --output artifacts/evaluation/example_gt_eval_suite_with_verification.md`
- `python apps/render_gt_eval_report.py --suite-json artifacts/evaluation/example_tracking_gt_eval_suite.json --output artifacts/evaluation/example_tracking_gt_eval_suite.md`
- `python -c "import sys; sys.path.insert(0, 'src'); import thesis3; print('ok')"`

관련:
- `src/thesis3/tracking_gt_evaluation.py`
- `src/thesis3/gt_eval_report.py`
- `apps/evaluate_tracking_gt.py`
- `apps/render_gt_eval_report.py`
- `examples/tracker_handoff_event_log.example.jsonl`
- `examples/tracking_frame_annotations_handoff.example.jsonl`
- `artifacts/evaluation/example_tracking_eval.json`
- `artifacts/evaluation/example_tracking_gt_eval_suite.json`
- `artifacts/evaluation/example_tracking_gt_eval_suite.md`
- `artifacts/evaluation/example_gt_eval_suite_with_verification.md`

### verification GT evaluation 추가

- `src/thesis3/verification_gt_evaluation.py`와 `apps/evaluate_verification_gt.py`를 추가해서 `verification_request` / `verification_result`를 verification camera frame GT와 직접 비교할 수 있게 정리
- request/result를 `request_id`로 묶고, target camera / target timestamp / roi_hint 또는 supporting_bbox 기준으로 frame GT를 찾아 `true_accept`, `false_accept`, `false_reject`, `true_reject`를 계산
- `src/thesis3/gt_eval_suite.py`와 `apps/run_gt_eval_suite.py`도 확장해서 event / frame / verification metric을 같은 matrix에서 같이 볼 수 있게 보강
- smoke fixture로 `examples/replay_verification_frame_annotations.example.jsonl`를 추가했고, dynamic plugin replay 기준으로 2 true accept + 1 true reject 경로를 확인
- `total_log/annotation_gt_playbook.md`에 verification evaluator 사용 예시를 추가

검증:
- `python -m compileall src apps`
- `python apps/run_offline_replay.py --config configs/scenario_dynamic_plugin.example.json`
- `python apps/evaluate_verification_gt.py --event-log artifacts/scenario_dynamic_plugin/scenario_a-36a84622.jsonl --frames examples/replay_verification_frame_annotations.example.jsonl --output artifacts/evaluation/example_replay_verification_eval.json`
- `python apps/run_gt_eval_suite.py --entry dynamic=artifacts/scenario_dynamic_plugin/scenario_a-36a84622.jsonl --events examples/replay_event_annotations.example.jsonl --verification-frames examples/replay_verification_frame_annotations.example.jsonl --output artifacts/evaluation/example_gt_eval_suite_with_verification.json`
- `python -c "import sys; sys.path.insert(0, 'src'); import thesis3; print('ok')"`

관련:
- `src/thesis3/verification_gt_evaluation.py`
- `src/thesis3/gt_eval_suite.py`
- `apps/evaluate_verification_gt.py`
- `apps/run_gt_eval_suite.py`
- `examples/replay_verification_frame_annotations.example.jsonl`
- `artifacts/evaluation/example_replay_verification_eval.json`
- `artifacts/evaluation/example_gt_eval_suite_with_verification.json`

### frame-level GT evaluation 및 GT eval suite 추가

- `src/thesis3/frame_gt_evaluation.py`와 `apps/evaluate_frame_gt.py`를 추가해서 event log의 `detector_result`를 frame bbox GT와 직접 비교할 수 있게 정리
- detector event에는 앞으로 `frame_id`, `camera_id`, `image_ref`, `timestamp`를 함께 남기도록 `src/thesis3/pipelines.py` logging payload를 보강해서 frame-level evaluator가 empty detection frame도 더 안정적으로 읽을 수 있게 함
- greedy IoU matching으로 TP / FN / FP, precision / recall, missing observation을 집계하고, negative frame도 `clean_negative` / `false_positive`로 볼 수 있게 정리
- `src/thesis3/gt_eval_suite.py`와 `apps/run_gt_eval_suite.py`를 추가해서 여러 event log를 같은 event/frame GT로 한 번에 비교하는 matrix output을 만들 수 있게 함
- smoke fixture로 `examples/replay_frame_annotations_oracle.example.jsonl`, `examples/replay_event_annotations_oracle.example.jsonl`를 추가
- `total_log/annotation_gt_playbook.md`에 frame evaluator와 GT eval suite 사용 예시를 추가

검증:
- `python -m compileall src apps`
- `python apps/run_offline_replay.py --config /tmp/scenario_gt_oracle_eval.json`
- `python apps/evaluate_frame_gt.py --event-log artifacts/scenario_gt_oracle/scenario_a-a9c9f370.jsonl --frames examples/replay_frame_annotations_oracle.example.jsonl --output artifacts/evaluation/example_replay_frame_eval.json`
- `python apps/run_gt_eval_suite.py --entry oracle=artifacts/scenario_gt_oracle/scenario_a-a9c9f370.jsonl --events examples/replay_event_annotations_oracle.example.jsonl --frames examples/replay_frame_annotations_oracle.example.jsonl --output artifacts/evaluation/example_gt_eval_suite.json`
- `python -c "import sys; sys.path.insert(0, 'src'); import thesis3; print('ok')"`

관련:
- `src/thesis3/frame_gt_evaluation.py`
- `src/thesis3/gt_eval_suite.py`
- `src/thesis3/pipelines.py`
- `apps/evaluate_frame_gt.py`
- `apps/run_gt_eval_suite.py`
- `examples/replay_frame_annotations_oracle.example.jsonl`
- `examples/replay_event_annotations_oracle.example.jsonl`
- `artifacts/evaluation/example_replay_frame_eval.json`
- `artifacts/evaluation/example_gt_eval_suite.json`

### event-level GT evaluation scaffold 추가

- `src/thesis3/gt_evaluation.py`와 `apps/evaluate_event_gt.py`를 추가해서 event log의 `decision_record`를 event-level GT와 직접 비교할 수 있게 정리
- 기본 기준은 `bird_present` positive, `bird_absent` / `hard_negative` negative, `unknown` ignored이고, 기본 alert action은 `REVIEW_REQUIRED`, `SIMULATED_ACTION`, `BLOCKED_BY_SAFETY_GATE`로 둠
- summary에서 positive hit/miss, negative clean/false-alert, unmatched alert decision을 바로 볼 수 있게 했고 per-event match도 JSON으로 남기게 함
- `examples/replay_event_annotations.example.jsonl`를 추가해서 current replay example과 맞는 event GT smoke fixture를 같이 남김
- `total_log/annotation_gt_playbook.md`에도 event-level evaluator 사용 예시를 추가해서 GT 생성 후 baseline 평가 루프를 문서로 연결

검증:
- `python -m compileall src apps`
- `python apps/run_offline_replay.py --config configs/scenario_detector_only_baseline.example.json`
- `python apps/evaluate_event_gt.py --event-log artifacts/scenario_detector_only_baseline/scenario_a-9b2a051a.jsonl --events examples/replay_event_annotations.example.jsonl --output artifacts/evaluation/example_replay_event_eval.json`
- `python -c "import sys; sys.path.insert(0, 'src'); import thesis3; print('ok')"`

관련:
- `src/thesis3/gt_evaluation.py`
- `apps/evaluate_event_gt.py`
- `examples/replay_event_annotations.example.jsonl`
- `artifacts/evaluation/example_replay_event_eval.json`
- `total_log/annotation_gt_playbook.md`

### annotation adjudication task export 추가

- `src/thesis3/annotation_adjudication.py`와 `apps/export_adjudication_tasks.py`를 추가해서 unresolved annotation을 reviewer handoff용 task JSONL로 바로 export할 수 있게 정리
- `pending`은 `primary_review`, `needs_second_review`는 `second_review`로 매핑하고, `primary_annotator` / `secondary_reviewer` 역할 힌트를 task에 같이 남기도록 구현
- event/frame 모두 지원하고, `unknown_label`, `unknown_object`, `ambiguity_reasons`를 priority와 reason tag로 같이 묶어 task queue를 만들 수 있게 함
- `total_log/annotation_gt_playbook.md`에 adjudication 운영 흐름과 reviewer queue export 예시를 추가

검증:
- `python -m compileall src apps`
- `python apps/export_adjudication_tasks.py --events examples/event_annotations_unknown.example.jsonl --frames examples/frame_annotations_unknown.example.jsonl --output-tasks artifacts/annotations/example_adjudication_tasks.jsonl --output-summary artifacts/annotations/example_adjudication_task_summary.json`

관련:
- `src/thesis3/annotation_adjudication.py`
- `apps/export_adjudication_tasks.py`
- `artifacts/annotations/example_adjudication_tasks.jsonl`
- `artifacts/annotations/example_adjudication_task_summary.json`
- `total_log/annotation_gt_playbook.md`

### unknown / ambiguous annotation adjudication 요약 도구 추가

- `unknown`을 단순 label로만 두지 않고 `metadata.ambiguity_reasons`, `metadata.adjudication_status`까지 같이 다루도록 `src/thesis3/annotation_rules.py` vocabulary와 validation 규칙을 확장
- `unknown` event에는 ambiguity reason과 adjudication status를 권장하도록 warning rule을 넣고, frame 쪽도 `class_name=\"unknown\"`일 때 ambiguity metadata를 확인하도록 정리
- `src/thesis3/annotation_queue.py`와 `apps/summarize_annotation_queue.py`를 추가해서 unresolved event / frame 수, ambiguity reason 분포, adjudication status 분포를 바로 집계할 수 있게 함
- clean smoke를 위해 `examples/event_annotations_unknown.example.jsonl`, `examples/frame_annotations_unknown.example.jsonl` example fixture를 추가
- `total_log/annotation_gt_playbook.md`에 unknown 운영 규칙, ambiguity reason 예시, adjudication status 예시, queue summary 사용 위치를 반영

검증:
- `python -m compileall src apps`
- `python apps/validate_annotations.py --events examples/event_annotations_unknown.example.jsonl --frames examples/frame_annotations_unknown.example.jsonl --video-index examples/annotation_video_assets.example.jsonl --output artifacts/annotations/example_unknown_validation.json`
- `python apps/summarize_annotation_queue.py --events examples/event_annotations_unknown.example.jsonl --frames examples/frame_annotations_unknown.example.jsonl --output artifacts/annotations/example_unknown_queue_summary.json`

관련:
- `src/thesis3/annotation_rules.py`
- `src/thesis3/annotation_queue.py`
- `apps/summarize_annotation_queue.py`
- `examples/event_annotations_unknown.example.jsonl`
- `examples/frame_annotations_unknown.example.jsonl`
- `artifacts/annotations/example_unknown_validation.json`
- `artifacts/annotations/example_unknown_queue_summary.json`
- `total_log/annotation_gt_playbook.md`

### annotation vocabulary / GT validation 도구 추가

- `src/thesis3/annotation_rules.py`와 `apps/validate_annotations.py`를 추가해서 event / frame annotation JSONL에 대해 기본 GT 규칙 검사를 자동화
- 기본 vocabulary는 `event_quality_tags`, `frame_object_tags`, `visibility_values`, `class_names`로 나눠 관리하고, `configs/annotation_vocabulary.template.json`으로 현장별 override를 할 수 있게 정리
- validator는 negative timestamp, inverted time range, bird count inconsistency, unknown tag/class/visibility, frame bbox 유효성, source event reference, asset / camera / source_path / duration consistency를 점검
- 예제 annotation smoke에서는 구조 오류 없이 통과했고, asset index 없이 돌린 예제라 `missing_asset_for_event`, `missing_asset_for_frame` warning만 남는 것을 확인
- `examples/annotation_video_assets.example.jsonl`를 추가해서 asset consistency까지 포함한 clean smoke 경로도 같이 남김
- `total_log/annotation_gt_playbook.md`에 validator 사용 예시와 QA 체크 항목을 추가해서 GT 생성 후 검증 루틴까지 문서로 연결

검증:
- `python -m compileall src apps`
- `python apps/validate_annotations.py --events examples/event_annotations.example.jsonl --frames examples/frame_annotations.example.jsonl --output artifacts/annotations/example_validation.json`
- `python apps/validate_annotations.py --events examples/event_annotations.example.jsonl --frames examples/frame_annotations.example.jsonl --video-index examples/annotation_video_assets.example.jsonl --output artifacts/annotations/example_validation_with_assets.json`

관련:
- `src/thesis3/annotation_rules.py`
- `apps/validate_annotations.py`
- `configs/annotation_vocabulary.template.json`
- `examples/annotation_video_assets.example.jsonl`
- `artifacts/annotations/example_validation.json`
- `artifacts/annotations/example_validation_with_assets.json`
- `total_log/annotation_gt_playbook.md`

### stress preset 기반 method comparison suite 및 GT playbook 추가

- `apps/run_method_stress_suite.py`를 추가해서 baseline / bird-sahi / ccs-lcs example config를 stress manifest별로 자동 재작성하고, readiness check 후 suite를 실행할 수 있게 정리
- 실행 결과는 `suite_records.jsonl`, `compact_summary.json`, `matrix.json`으로 남겨서 stress profile별로 어떤 방법이 review-heavy한지, 어떤 reason counter가 튀는지 바로 비교할 수 있게 함
- smoke 기준으로 `sync_jitter`, `quality_drop`, `mixed_faults`에서 baseline / bird-sahi / ccs-lcs 비교가 정상 실행됨
- `total_log/annotation_gt_playbook.md`를 추가해서 event-level GT 우선, subset frame bbox, negative / hard negative 포함, split / QA 규칙, 현재 도구와의 연결 순서를 운영 문서로 고정

검증:
- `python -m compileall src apps`
- `python apps/run_method_stress_suite.py --preset sync_jitter --preset quality_drop --preset mixed_faults --output-dir artifacts/suites/method_stress_demo_smoke`

관련:
- `apps/run_method_stress_suite.py`
- `artifacts/suites/method_stress_demo_smoke/suite_records.jsonl`
- `artifacts/suites/method_stress_demo_smoke/compact_summary.json`
- `artifacts/suites/method_stress_demo_smoke/matrix.json`
- `total_log/annotation_gt_playbook.md`

## 2026-04-04

### camera inventory 운영형 필드 확장

- camera inventory에 `installation_id`, `safe_zone_ref`, `stream_uri_ref`, `mount_height_m`, `view_direction_deg`, `is_ptz`를 추가해서 실제 현장 운영 정보를 수용할 수 있게 확장
- bootstrap camera setup이 이제 site 기준 placeholder ref를 자동 생성해서 inventory 템플릿만으로도 운영형 field shape를 바로 볼 수 있게 정리
- canonical export는 이 운영형 필드를 frame/sequence metadata에 같이 넣어 이후 replay, report, live adapter가 동일 metadata를 참조할 수 있게 함
- data audit는 inventory coverage 외에도 `missing_installation_id`, `missing_safe_zone_ref`, `missing_stream_uri_ref`, `invalid_mount_height`, `invalid_view_direction`를 점검하도록 보강
- current smoke setup에서는 source_type이 `mp4`라 stream ref missing warning은 내지 않고, bootstrap placeholder가 들어간 inventory 기준으로 issue 없이 통과함

검증:
- `python -m compileall src apps`
- `python apps/bootstrap_camera_setup.py --video-assets /tmp/thesis3_smoke/video_assets_both.jsonl --output-dir artifacts/camera_setup/example --site-id smoke_site --environment-tag prearrival_mock --timezone Asia/Seoul`
- `python apps/run_data_audit.py --video-assets /tmp/thesis3_smoke/video_assets_both.jsonl --sample-frames-per-asset 1 --camera-inventory artifacts/camera_setup/example/camera_inventory.jsonl --calibration-registry artifacts/camera_setup/example/calibration_registry.jsonl --output artifacts/audit/example_mp4_assets_with_camera_setup_audit.json`
- `python apps/export_canonical_dataset.py --replay-manifest examples/replay_manifest.jsonl --output-dir artifacts/canonical/example_replay_with_camera_setup --environment-tag fallback_env --camera-inventory artifacts/camera_setup/example/camera_inventory.jsonl --calibration-registry artifacts/camera_setup/example/calibration_registry.jsonl`

관련:
- `src/thesis3/camera_inventory.py`
- `src/thesis3/canonical_data.py`
- `src/thesis3/data_audit.py`
- `apps/bootstrap_camera_setup.py`
- `artifacts/camera_setup/example/camera_inventory.jsonl`
- `artifacts/canonical/example_replay_with_camera_setup/canonical_frame_samples.jsonl`
- `artifacts/audit/example_mp4_assets_with_camera_setup_audit.json`

### camera inventory / calibration registry bootstrap 추가

- 실데이터 전 준비에서 빠지기 쉬운 `camera metadata / calibration`을 공통 인벤토리로 관리할 수 있도록 `camera_inventory.py`와 `bootstrap_camera_setup.py`를 추가
- MP4 asset index에서 `camera_inventory.jsonl`, `calibration_registry.jsonl` template를 자동 생성하게 했고, role / expected fps / expected resolution / calibration_ref 기본값을 같이 채우도록 정리
- canonical export는 이제 optional `camera_inventory`, `calibration_registry`를 읽어서 `camera_role`, `site_id`, `timezone`, `calibration_ref`를 canonical records에 함께 남긴다
- data audit도 inventory/regsitry를 읽어서 coverage, missing calibration_ref, expected fps/resolution mismatch를 같이 점검하도록 보강
- smoke 기준으로 two-camera setup에서 camera inventory coverage는 정상이고, replay audit의 issue 6건은 inventory 누락이 아니라 example manifest의 `image_ref` 미존재 때문임을 확인

검증:
- `python -m compileall src apps`
- `ffmpeg -loglevel error -y -framerate 5 -pattern_type glob -i 'artifacts/live_spool_test/cam_tele/*.jpg' -c:v libx264 /tmp/thesis3_smoke/cam_tele.mp4`
- `python apps/index_mp4_corpus.py --input /tmp/thesis3_smoke --output /tmp/thesis3_smoke/video_assets_both.jsonl --camera-strategy stem`
- `python apps/bootstrap_camera_setup.py --video-assets /tmp/thesis3_smoke/video_assets_both.jsonl --output-dir artifacts/camera_setup/example --site-id smoke_site --environment-tag prearrival_mock --timezone Asia/Seoul`
- `python apps/export_canonical_dataset.py --video-assets /tmp/thesis3_smoke/video_assets_both.jsonl --output-dir artifacts/canonical/example_with_camera_setup --environment-tag fallback_env --camera-inventory artifacts/camera_setup/example/camera_inventory.jsonl --calibration-registry artifacts/camera_setup/example/calibration_registry.jsonl`
- `python apps/run_data_audit.py --video-assets /tmp/thesis3_smoke/video_assets_both.jsonl --sample-frames-per-asset 1 --camera-inventory artifacts/camera_setup/example/camera_inventory.jsonl --calibration-registry artifacts/camera_setup/example/calibration_registry.jsonl --output artifacts/audit/example_mp4_assets_with_camera_setup_audit.json`
- `python apps/export_canonical_dataset.py --replay-manifest examples/replay_manifest.jsonl --output-dir artifacts/canonical/example_replay_with_camera_setup --environment-tag fallback_env --camera-inventory artifacts/camera_setup/example/camera_inventory.jsonl --calibration-registry artifacts/camera_setup/example/calibration_registry.jsonl`
- `python apps/run_data_audit.py --replay-manifest examples/replay_manifest.jsonl --camera-inventory artifacts/camera_setup/example/camera_inventory.jsonl --calibration-registry artifacts/camera_setup/example/calibration_registry.jsonl --output artifacts/audit/example_replay_with_camera_setup_audit.json`

관련:
- `src/thesis3/camera_inventory.py`
- `apps/bootstrap_camera_setup.py`
- `artifacts/camera_setup/example/camera_inventory.jsonl`
- `artifacts/camera_setup/example/calibration_registry.jsonl`
- `artifacts/canonical/example_replay_with_camera_setup/canonical_frame_samples.jsonl`
- `artifacts/audit/example_replay_with_camera_setup_audit.json`

### canonical schema / data audit / stress replay 준비 추가

- 실데이터 전 준비를 위해 `canonical_data`, `data_audit`, `stress` 모듈을 추가
- `export_canonical_dataset.py`로 indexed MP4 asset은 canonical sequence로, replay manifest는 canonical frame sample로 바로 변환 가능하게 정리
- `run_data_audit.py`로 raw MP4 asset index 또는 replay manifest에 대해 메타데이터 audit을 돌릴 수 있게 했고, MP4 자산은 선택적으로 sampled frame brightness / contrast / sharpness까지 같이 뽑도록 준비
- `generate_stress_replay.py`로 `sync_jitter`, `quality_drop`, `camera_dropout`, `latency_spike`, `mixed_faults` preset replay manifest를 생성할 수 있게 해서 synthetic perturbation 기반 stress test 출발점을 마련
- 예제 replay manifest 기준 canonical export, replay audit, stress manifest generation이 모두 통과했고, 임시 MP4 asset 기준 canonical sequence export와 sampled-frame audit도 통과

검증:
- `python -m compileall src apps`
- `python apps/export_canonical_dataset.py --replay-manifest examples/replay_manifest.jsonl --output-dir artifacts/canonical/example_replay --environment-tag prearrival_mock`
- `python apps/run_data_audit.py --replay-manifest examples/replay_manifest.jsonl --output artifacts/audit/example_replay_audit.json`
- `python apps/generate_stress_replay.py --input-manifest examples/replay_manifest.jsonl --output-dir artifacts/stress/example_replay --preset sync_jitter --preset quality_drop --preset mixed_faults --seed 7`
- `ffmpeg -loglevel error -y -framerate 5 -pattern_type glob -i 'artifacts/live_spool_test/cam_wide/*.jpg' -c:v libx264 /tmp/thesis3_smoke/cam_wide.mp4`
- `python apps/index_mp4_corpus.py --input /tmp/thesis3_smoke/cam_wide.mp4 --output /tmp/thesis3_smoke/video_assets.jsonl --camera-strategy stem`
- `python apps/export_canonical_dataset.py --video-assets /tmp/thesis3_smoke/video_assets.jsonl --output-dir artifacts/canonical/example_mp4_assets --environment-tag prearrival_mock`
- `python apps/run_data_audit.py --video-assets /tmp/thesis3_smoke/video_assets.jsonl --sample-frames-per-asset 2 --output artifacts/audit/example_mp4_assets_audit.json`

관련:
- `src/thesis3/canonical_data.py`
- `src/thesis3/data_audit.py`
- `src/thesis3/stress.py`
- `apps/export_canonical_dataset.py`
- `apps/run_data_audit.py`
- `apps/generate_stress_replay.py`
- `artifacts/canonical/example_replay/canonical_frame_samples.jsonl`
- `artifacts/canonical/example_mp4_assets/canonical_sequences.jsonl`
- `artifacts/audit/example_replay_audit.json`
- `artifacts/audit/example_mp4_assets_audit.json`
- `artifacts/stress/example_replay/summary.json`

### bird-sahi local operating point sweep 및 tuned profile 추가

- `bird_sahi_new` env 기준으로 bird-sahi confirmation operating point를 빠르게 비교할 수 있는 sweep runner를 추가
- `confirm_len`, `min_verifier_score`, `verifier score_threshold`, `interval`, `bootstrap_first_n`, `use_track_local_index`를 조합해 generated config를 만들고 readiness + suite를 한 번에 실행하도록 정리
- small sweep 결과에서는 confirm 계열의 주요 차이가 threshold보다 `confirm_len`에서 크게 갈렸고, `confirm_len=1`이 `confirm_len=2`보다 review burden이 훨씬 낮았다
- 이 결과를 바탕으로 `scenario_bird_sahi_method_bundle_tuned.local.json`을 추가해서 local confirm 기본 operating point를 `confirm_len=1`로 조정
- `apps/run_bird_sahi_focus_suite.py`에는 `local_tuned` profile을 추가해서 baseline / tuned confirm / no-confirm을 바로 비교할 수 있게 함
- tuned confirm local은 현재 toy replay 기준으로 `SIMULATED_ACTION 3 / REVIEW_REQUIRED 1`, verification request 3건으로, 이전 confirm local보다 review-heavy하지 않은 상태다

검증:
- `python -m compileall src apps`
- `conda run -n bird_sahi_new python apps/run_bird_sahi_operating_point_sweep.py --include-noconfirm --confirm-len 1 --confirm-len 2 --min-verifier-score 0.70 --min-verifier-score 0.74 --verifier-score-threshold 0.70 --verifier-score-threshold 0.74 --interval 4 --bootstrap-first-n 2 --use-track-local-index true --output-dir artifacts/sweeps/bird_sahi_local_small_sweep`
- `conda run -n bird_sahi_new python apps/run_bird_sahi_focus_suite.py --profile local_tuned --output artifacts/suites/bird_sahi_focus_local_tuned.jsonl`

관련:
- `apps/run_bird_sahi_operating_point_sweep.py`
- `apps/run_bird_sahi_focus_suite.py`
- `configs/scenario_bird_sahi_method_bundle_tuned.local.json`
- `artifacts/sweeps/bird_sahi_local_small_sweep/ranking.json`
- `artifacts/suites/bird_sahi_focus_local_tuned.jsonl`

## 2026-04-03

### 방법론 훅 구조 추가

- detector / trigger / selector 외에 `verification_scheduler`, `confirmation_policy`, `environment profile`을 config 경계로 추가
- baseline detector-only와 방법론 variant를 같은 pipeline skeleton 위에서 비교할 수 있게 정리
- `bird_sahi_temporal`, `ccs-lcs`를 고정 구조가 아니라 이후 번역해 넣을 수 있는 방법론 슬롯을 확보

검증:
- `python -m compileall src apps examples`
- `python -c "import sys; sys.path.insert(0, 'src'); import thesis3; print('ok')"`
- `python apps/run_offline_replay.py --config configs/scenario_a.example.json`
- `python apps/run_offline_replay.py --config configs/scenario_b.example.json`
- `python apps/run_offline_replay.py --config configs/scenario_bird_sahi_detector.example.json`

관련:
- `src/thesis3/core.py`
- `src/thesis3/methodology.py`
- `src/thesis3/runtime.py`
- `src/thesis3/pipelines.py`

### detector-only baseline 및 method-hook 예제 추가

- detector-only baseline example config 추가
- custom verification scheduler / confirmation policy 예제 추가
- environment-aware method variant config 추가

검증:
- `python apps/run_offline_replay.py --config configs/scenario_detector_only_baseline.example.json`
- `python apps/run_offline_replay.py --config configs/scenario_methodology_hooks.example.json`
- `python apps/run_experiment_suite.py --config configs/scenario_detector_only_baseline.example.json --config configs/scenario_methodology_hooks.example.json --config configs/scenario_bird_sahi_detector.example.json --output artifacts/suites/flexible_methods_smoke.jsonl`

관련:
- `configs/scenario_detector_only_baseline.example.json`
- `configs/scenario_methodology_hooks.example.json`
- `examples/custom_plugins.py`

### 연구 방법 번들 슬롯 추가

- `safety_policy` 슬롯을 추가해서 `ccs-lcs`류 방법을 verifier가 아니라 safety gate 뒤쪽 방법론으로 연결할 수 있게 함
- `bird_sahi_temporal_local_verifier`를 추가해서 detector가 아니라 local crop verifier backend로 붙일 수 있게 함
- bird-sahi bundle, ccs-lcs bundle 예제와 real template config 추가

검증:
- `python -m compileall src`
- `python apps/run_offline_replay.py --config configs/scenario_bird_sahi_method_bundle.example.json`
- `python apps/run_offline_replay.py --config configs/scenario_ccs_lcs_safety_bundle.example.json`
- `python apps/run_experiment_suite.py --config configs/scenario_detector_only_baseline.example.json --config configs/scenario_bird_sahi_method_bundle.example.json --config configs/scenario_ccs_lcs_safety_bundle.example.json --output artifacts/suites/method_bundle_smoke.jsonl`

관련:
- `src/thesis3/safety.py`
- `src/thesis3/research_repo_adapters.py`
- `src/thesis3/runtime.py`
- `src/thesis3/pipelines.py`
- `configs/scenario_bird_sahi_method_bundle.example.json`
- `configs/scenario_bird_sahi_method_bundle.template.json`
- `configs/scenario_ccs_lcs_safety_bundle.example.json`
- `configs/scenario_ccs_lcs_safety_bundle.template.json`

### bird-sahi 전용 schedule / confirmation 정리

- `bird_sahi_always_verify_scheduler`, `bird_sahi_keyframe_verify_scheduler`, `bird_sahi_confirmation_policy` 추가
- bird-sahi bundle 예제를 generic periodic/streak 이름 대신 bird-sahi method 이름으로 정리
- no-confirm partial approximation example/template 추가
- local repo weight / mapping을 박아둔 `bird-sahi` local config 추가
- wrapper를 lazy-load로 바꿔서 `ultralytics` 미설치 환경에서도 config 검증과 metadata-fallback smoke test는 가능하게 함

검증:
- `python -m compileall src configs`
- `python apps/run_offline_replay.py --config configs/scenario_bird_sahi_method_bundle.example.json`
- `python apps/run_offline_replay.py --config configs/scenario_bird_sahi_noconfirm.example.json`
- `python apps/run_experiment_suite.py --config configs/scenario_detector_only_baseline.example.json --config configs/scenario_bird_sahi_method_bundle.example.json --config configs/scenario_bird_sahi_noconfirm.example.json --output artifacts/suites/bird_sahi_focus_smoke.jsonl`
- `python apps/run_offline_replay.py --config configs/scenario_bird_sahi_noconfirm.local.json`
- `python apps/run_offline_replay.py --config configs/scenario_bird_sahi_method_bundle.local.json`

관련:
- `src/thesis3/methodology.py`
- `src/thesis3/research_repo_adapters.py`
- `configs/scenario_bird_sahi_method_bundle.example.json`
- `configs/scenario_bird_sahi_method_bundle.template.json`
- `configs/scenario_bird_sahi_method_bundle.local.json`
- `configs/scenario_bird_sahi_noconfirm.example.json`
- `configs/scenario_bird_sahi_noconfirm.template.json`
- `configs/scenario_bird_sahi_noconfirm.local.json`

### config readiness checker 및 bird-sahi suite helper 추가

- config 실행 전에 manifest, weights, class mapping, external target symbol, plugin instantiation 상태를 확인하는 readiness checker 추가
- lazy-load wrapper만으로는 놓치기 쉬운 nested external backend instantiation도 같이 검사하도록 구현
- bird-sahi 전용으로 baseline vs confirmation 포함 bundle vs no-confirm variant를 한 번에 점검하고 실행하는 suite helper 추가
- local bird-sahi config는 현재 `ultralytics` 미설치 때문에 readiness 단계에서 `not ready`로 잡히는 것을 확인

검증:
- `python -m compileall src apps`
- `python apps/check_config_readiness.py --config configs/scenario_bird_sahi_method_bundle.example.json --config configs/scenario_bird_sahi_noconfirm.example.json`
- `python apps/check_config_readiness.py --config configs/scenario_bird_sahi_method_bundle.local.json --config configs/scenario_bird_sahi_noconfirm.local.json`
- `python apps/run_bird_sahi_focus_suite.py --profile demo --check-only`
- `python apps/run_bird_sahi_focus_suite.py --profile demo --output artifacts/suites/bird_sahi_focus_demo_smoke.jsonl`
- `python apps/run_bird_sahi_focus_suite.py --profile local --check-only`

관련:
- `src/thesis3/readiness.py`
- `apps/check_config_readiness.py`
- `apps/run_bird_sahi_focus_suite.py`
- `artifacts/suites/bird_sahi_focus_demo_smoke.jsonl`

### 기존 conda env 재사용 경로 정리

- 설치된 conda env를 확인한 결과 `bird_sahi_new`, `bird_repel`에는 `ultralytics 8.3.235`가 있고 `base`, `lvr-infer`에는 없다
- 대신 `bird_sahi_new`, `bird_repel`은 Python 3.9라서 기존 `@dataclass(slots=True)`가 바로는 실행되지 않았다
- `src/thesis3/dataclass_compat.py`를 추가하고 관련 dataclass import를 compatibility wrapper로 바꿔서 Python 3.9에서도 실행 가능하게 맞춤
- 그 결과 `conda run -n bird_sahi_new` 기준으로 bird-sahi local readiness와 local focus suite가 정상 실행됨
- bird-sahi 쪽 표준 실행 env는 우선 `bird_sahi_new`로 두는 것이 자연스럽다

검증:
- `conda env list`
- `conda run -n bird_sahi_new python -c "import ultralytics; print(ultralytics.__version__)"`
- `conda run -n bird_repel python -c "import ultralytics; print(ultralytics.__version__)"`
- `conda run -n bird_sahi_new python -c "import sys; sys.path.insert(0, 'src'); import thesis3; print('ok')"`
- `conda run -n bird_sahi_new python apps/check_config_readiness.py --config configs/scenario_bird_sahi_method_bundle.local.json --config configs/scenario_bird_sahi_noconfirm.local.json`
- `conda run -n bird_sahi_new python apps/run_bird_sahi_focus_suite.py --profile local --check-only`
- `conda run -n bird_sahi_new python apps/run_bird_sahi_focus_suite.py --profile local --output artifacts/suites/bird_sahi_focus_local_env_smoke.jsonl`

관련:
- `src/thesis3/dataclass_compat.py`
- `src/thesis3/core.py`
- `src/thesis3/methodology.py`
- `src/thesis3/safety.py`
- `src/thesis3/readiness.py`
- `apps/check_config_readiness.py`
- `apps/run_bird_sahi_focus_suite.py`
- `artifacts/suites/bird_sahi_focus_local_env_smoke.jsonl`

### runtime environment 메타데이터 기록 추가

- `run_start` 이벤트에 `runtime_env`를 남기도록 해서 `conda_default_env`, `python_executable`, `python_version`, `cwd`를 같이 기록
- readiness report 헤더에도 현재 env와 interpreter가 보이도록 추가
- suite summary에도 `run_context.runtime_env`가 들어가서 나중에 결과 비교 시 환경 차이를 같이 볼 수 있게 함

검증:
- `python apps/check_config_readiness.py --config configs/scenario_detector_only_baseline.example.json`
- `conda run -n bird_sahi_new python apps/check_config_readiness.py --config configs/scenario_bird_sahi_method_bundle.local.json`
- `conda run -n bird_sahi_new python apps/run_bird_sahi_focus_suite.py --profile local --output artifacts/suites/bird_sahi_focus_local_env_smoke_v2.jsonl`

관련:
- `src/thesis3/runtime_env.py`
- `src/thesis3/runtime.py`
- `src/thesis3/readiness.py`
- `src/thesis3/reporting.py`
- `artifacts/suites/bird_sahi_focus_local_env_smoke_v2.jsonl`

### bird-sahi operating point 분석 가능하게 보강

- `bird_sahi_keyframe_verify_scheduler`에 `bootstrap_first_n`, `use_track_local_index` 옵션을 추가해서 짧은 replay에서도 confirm path를 실제로 태워볼 수 있게 함
- local confirm config는 bootstrap verify 2회를 먼저 허용하도록 조정해서 더 이상 `forced_keyframe_skip`만 반복되지 않게 함
- event log summary에 `trigger_reasons`, `verification_schedule_reasons`, `confirmation_reasons`, `verification_outcomes`, `verification_failure_reasons`, `safety_policy_reasons`를 추가
- 그 결과 local confirm bundle은 이제 verification request 3건, `bird_sahi_confirmation_passed` 1건, `bird_sahi_confirmation_pending` 2건이 summary에서 바로 보인다

검증:
- `python -m compileall src apps`
- `conda run -n bird_sahi_new python apps/run_offline_replay.py --config configs/scenario_bird_sahi_method_bundle.local.json`
- `conda run -n bird_sahi_new python apps/run_bird_sahi_focus_suite.py --profile local --output artifacts/suites/bird_sahi_focus_local_env_smoke_v3.jsonl`

관련:
- `src/thesis3/methodology.py`
- `src/thesis3/reporting.py`
- `configs/scenario_bird_sahi_method_bundle.local.json`
- `configs/scenario_bird_sahi_method_bundle.template.json`
- `artifacts/suites/bird_sahi_focus_local_env_smoke_v3.jsonl`

## 2026-04-02

### 시스템 베이스 정리

- detector / verifier / tracker plugin 구조를 갖춘 기본 시스템 베이스 추가
- scenario A / B pipeline skeleton 작성
- policy gate, actuator simulator, event logging, report 요약 추가
- offline replay runner 실행 가능 상태 확인

관련:
- `apps/run_offline_replay.py`
- `src/thesis3/runtime.py`
- `src/thesis3/pipelines.py`
- `src/thesis3/components.py`

### latency / burden 측정 추가

- detector / tracker / verification / policy / actuator latency 기록
- source-to-decision latency 기록
- verification burden, review rate, blocked rate 요약 추가

관련:
- `src/thesis3/core.py`
- `src/thesis3/pipelines.py`
- `src/thesis3/reporting.py`

### MP4 기반 데이터 준비 흐름 추가

- MP4 인덱싱 도구 추가
- clip task 생성
- event annotation / frame annotation / experiment sample schema 추가
- frame label task 생성 및 experiment manifest 생성 도구 추가

관련:
- `src/thesis3/video_probe.py`
- `src/thesis3/video_data.py`
- `apps/index_mp4_corpus.py`
- `apps/generate_clip_tasks.py`
- `apps/generate_frame_label_tasks.py`
- `apps/build_experiment_manifest.py`

### annotation 및 replay export 추가

- clip preview mp4 생성
- review html 생성
- event annotation template 생성
- experiment manifest에서 frame 추출 및 replay manifest 생성

관련:
- `src/thesis3/video_annotation_pack.py`
- `src/thesis3/video_replay_export.py`
- `apps/export_annotation_pack.py`
- `apps/export_replay_from_experiment.py`

### image-backed baseline 추가

- GT metadata detector / verifier
- mean-intensity detector
- crop variance verifier
- 실제 `image_ref`를 읽는 baseline 경로 검증

관련:
- `src/thesis3/image_io.py`
- `src/thesis3/components.py`
- `configs/scenario_gt_oracle.template.json`
- `configs/scenario_image_stat.template.json`

### live / pseudo-live 입력 추가

- ffmpeg 기반 file-stream / RTSP live source scaffold 추가
- live grouped packet -> 기존 scenario pipeline 연결
- pseudo-live mp4로 end-to-end 실행 검증

관련:
- `src/thesis3/live_stream.py`
- `src/thesis3/live_runtime.py`
- `apps/run_live_stream.py`
- `configs/live_file_stream.template.json`
- `configs/live_rtsp_stream.template.json`

### 교체 실험용 모듈화 추가

- detector / verifier / tracker 외에 trigger policy / candidate selector도 모듈 경계로 분리
- registry 이름뿐 아니라 `module_or_path:Symbol` 형태의 dynamic plugin 로딩 추가
- 여러 config를 한 번에 실행해서 결과를 모을 수 있는 suite runner 추가
- 외부 플러그인 예제와 runnable example config 추가

검증:
- `python -m compileall src apps`
- `python apps/run_offline_replay.py --config configs/scenario_a.example.json`
- `python apps/run_offline_replay.py --config configs/scenario_dynamic_plugin.example.json`
- `python apps/run_offline_replay.py --config configs/scenario_b_dynamic_plugin.example.json`
- `python apps/run_experiment_suite.py --config configs/scenario_a.example.json --config configs/scenario_dynamic_plugin.example.json --config configs/scenario_b_dynamic_plugin.example.json --output artifacts/suites/modular_smoke.jsonl`
- `python apps/run_live_stream.py --config /tmp/thesis3_mp4/live_file_stream.json --max-groups 4`

관련:
- `src/thesis3/plugin_loader.py`
- `src/thesis3/orchestration.py`
- `src/thesis3/runtime.py`
- `src/thesis3/pipelines.py`
- `src/thesis3/suite_runner.py`
- `apps/run_experiment_suite.py`
- `examples/custom_plugins.py`
- `configs/scenario_dynamic_plugin.example.json`
- `configs/scenario_b_dynamic_plugin.example.json`

### 외부 repo wrapper template 추가

- 외부 detector / verifier를 바로 감쌀 수 있는 generic adapter 추가
- `frame_packet`, `image_path`, `numpy_rgb`, `roi_array` 같은 입력 모드 지원
- foreign model output을 `DetectionCandidate` / `VerificationResult`로 바꾸는 helper 추가
- 복사해서 수정할 수 있는 detector / verifier wrapper template 추가
- demo foreign model과 example config를 함께 넣어 smoke test 가능하게 정리

검증:
- `python -m compileall src apps examples`
- `python apps/run_offline_replay.py --config configs/scenario_generic_external_wrapper.example.json`
- `python apps/run_offline_replay.py --config configs/scenario_template_external_wrapper.example.json`
- `python apps/run_experiment_suite.py --config configs/scenario_a.example.json --config configs/scenario_generic_external_wrapper.example.json --config configs/scenario_template_external_wrapper.example.json --output artifacts/suites/external_wrapper_smoke.jsonl`

관련:
- `src/thesis3/external_adapters.py`
- `src/thesis3/components.py`
- `examples/external_repo_models.py`
- `examples/external_repo_wrapper_template.py`
- `configs/scenario_generic_external_wrapper.example.json`
- `configs/scenario_template_external_wrapper.example.json`

### 실제 연구 repo detector 후보 연결 준비

- 워크스페이스 기준 detector 후보 repo inventory 수행
- `bird_repel` detector API와 `bird_sahi_temporal` YOLO wrapper API 확인
- 두 repo에 맞는 concrete detector wrapper 추가
- repo별 runnable smoke example config와 실제 연결용 template config 추가
- dynamic file plugin loader에서 dataclass가 깨지던 `sys.modules` 등록 버그 수정
- 외부 모델 온보딩 문서를 `total_log/external_model_onboarding.md`로 추가

검증:
- `python -m compileall src apps examples`
- `python apps/run_offline_replay.py --config configs/scenario_bird_repel_detector.example.json`
- `python apps/run_offline_replay.py --config configs/scenario_bird_sahi_detector.example.json`
- `python apps/run_experiment_suite.py --config configs/scenario_a.example.json --config configs/scenario_bird_repel_detector.example.json --config configs/scenario_bird_sahi_detector.example.json --output artifacts/suites/research_repo_wrapper_smoke.jsonl`

관련:
- `src/thesis3/research_repo_adapters.py`
- `src/thesis3/plugin_loader.py`
- `examples/repo_bridge_demo_models.py`
- `configs/scenario_bird_repel_detector.example.json`
- `configs/scenario_bird_repel_detector.template.json`
- `configs/scenario_bird_sahi_detector.example.json`
- `configs/scenario_bird_sahi_detector.template.json`
- `total_log/external_model_onboarding.md`

### 현재 판단

- 시스템 골격은 상당 부분 준비됨
- 실제 detector / verifier wrapper 연결이 다음 가장 중요한 단계
- 구조적으로는 필요한 부분만 바꿔 다시 실험하는 흐름이 가능해짐
- 실데이터 도착 전에는 canonical schema와 audit 준비가 필요

## 다음에 로그를 남길 때

- 날짜별로 새 섹션 추가
- 한 섹션 안에는 "무엇을 했는지", "검증했는지", "다음에 무엇을 할지"를 짧게 남기기
