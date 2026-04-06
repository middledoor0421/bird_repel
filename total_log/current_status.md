# 현재 시스템 상태

기준일: `2026-04-05`

## 0. 현재 모드

- 현재 상태는 `실데이터 수령 전 대기`이다.
- 실데이터가 오기 전까지 필요한 시스템 베이스, GT 운영/평가 뼈대, 방법론 교체 실험 구조는 대부분 준비된 상태다.
- 다음 본격 작업은 `실제 MP4/stream 첫 배치`, `camera/site metadata`, `현장 운영 규칙`이 들어오는 시점부터 재개한다.

## 1. 전체 상태 요약

현재 `thesis3`는 "실데이터가 들어왔을 때 바로 태워볼 수 있는 시스템 베이스"가 어느 정도 갖춰진 상태다.
아직 실제 연구용 detector/verifier 모델은 연결되지 않았지만, 다음 흐름은 이미 닫혀 있다.

1. offline replay 실행
2. policy / simulator / logging
3. MP4 -> annotation -> GT -> replay manifest 변환
4. image-backed baseline detector / verifier
5. pseudo-live stream 입력
6. detector / trigger policy / candidate selector 모듈 교체 실험
7. 외부 detector / verifier repo wrapper template 및 generic adapter
8. environment profile / verification scheduler / confirmation policy 훅 기반 방법론 교체 실험
9. canonical schema export / data audit / synthetic stress replay 준비
10. camera inventory / calibration registry bootstrap 준비
11. camera inventory에 운영형 필드 placeholder 추가
12. stress preset 기반 method comparison suite 추가
13. annotation / GT 운영 playbook 정리
14. annotation vocabulary / GT validation CLI 추가
15. unknown / ambiguous annotation adjudication summary 추가
16. annotation adjudication task export 추가
17. event-level GT evaluation scaffold 추가
18. frame-level GT evaluation 및 GT eval suite 추가
19. verification GT evaluation 추가
20. tracking / handoff GT evaluation 및 markdown report 추가

즉, 뼈대는 있고 실제 모델과 실데이터 규칙을 넣는 단계가 남아 있다.

현재 방향은 특정 연구 구조를 고정하는 것이 아니라, detector-only baseline은 유지하면서
중간 단계 방법론을 계속 교체할 수 있게 만드는 것이다.

실무적으로는 "사전 준비 단계는 거의 마감"으로 보고, 지금부터는 실제 데이터 도착 이후 적응 작업을 기다리는 상태로 본다.

## 1-1. 현재 구조 원칙

- detector-only baseline은 항상 유지한다.
- `bird_sahi_temporal`, `ccs-lcs`는 시스템의 영구 고정 뼈대가 아니라 교체 가능한 방법론 후보로 본다.
- 실제 데이터 적응에서 자주 바뀔 수 있는 부분은 detector보다 중간 단계일 가능성이 높다.
- 그래서 pipeline 전체를 자주 다시 쓰는 대신, 중간 훅을 바꾸는 구조를 우선한다.

## 2. 현재 구현된 것

### 시스템 베이스

- 공통 타입 및 config 구조
- detector / verifier / tracker plugin registry
- dynamic plugin loader
- scenario A / scenario B pipeline skeleton
- modular trigger policy / candidate selector
- environment profile
- verification scheduler / confirmation policy
- safety policy
- policy gate
- actuator simulator
- event log 저장 및 요약
- experiment suite runner
- config / external method readiness checker
- runtime environment metadata logging
- external detector / verifier generic adapter
- external repo wrapper template

관련 경로:
- `src/thesis3/core.py`
- `src/thesis3/components.py`
- `src/thesis3/external_adapters.py`
- `src/thesis3/methodology.py`
- `src/thesis3/orchestration.py`
- `src/thesis3/plugin_loader.py`
- `src/thesis3/pipelines.py`
- `src/thesis3/policy.py`
- `src/thesis3/events.py`
- `src/thesis3/reporting.py`
- `src/thesis3/suite_runner.py`
- `src/thesis3/readiness.py`
- `src/thesis3/runtime_env.py`
- `apps/run_experiment_suite.py`
- `apps/check_config_readiness.py`
- `total_log/external_model_onboarding.md`

### offline replay

- manifest 기반 replay runner
- timestamp tolerance 기반 grouping
- scenario별 replay 실행

관련 경로:
- `apps/run_offline_replay.py`
- `src/thesis3/replay.py`
- `src/thesis3/runtime.py`

### latency / burden 측정

- detector / tracker / verification / policy / actuator latency 기록
- source-to-decision latency 기록
- review rate / blocked rate / verification burden 집계

관련 경로:
- `src/thesis3/core.py`
- `src/thesis3/pipelines.py`
- `src/thesis3/reporting.py`

### MP4 데이터 준비 흐름

- MP4 인덱싱
- clip task 생성
- event GT 구조
- frame label task 생성
- experiment manifest 생성
- replay bundle export
- annotation pack export
- canonical sequence / frame sample export
- camera inventory / calibration registry template bootstrap
- camera inventory에 `installation_id`, `safe_zone_ref`, `stream_uri_ref`, `mount_height_m`, `view_direction_deg`, `is_ptz` 포함
- raw MP4 / replay manifest data audit
- synthetic perturbation 기반 stress replay generation
- baseline / bird-sahi / ccs-lcs stress comparison suite
- annotation / GT 운영 규칙 문서
- annotation vocabulary template
- event / frame GT validation CLI
- unresolved annotation queue summary CLI
- reviewer handoff용 adjudication task export CLI
- event-level GT vs event log evaluation CLI
- frame-level bbox GT vs detector observation evaluation CLI
- multi-run GT evaluation suite CLI
- verification_result vs verification-camera GT evaluation CLI
- tracker_update vs object-id GT tracking/handoff evaluation CLI
- GT eval suite markdown report renderer

관련 경로:
- `src/thesis3/video_probe.py`
- `src/thesis3/video_data.py`
- `src/thesis3/video_replay_export.py`
- `src/thesis3/video_annotation_pack.py`
- `src/thesis3/camera_inventory.py`
- `src/thesis3/canonical_data.py`
- `src/thesis3/data_audit.py`
- `src/thesis3/stress.py`
- `src/thesis3/annotation_queue.py`
- `src/thesis3/annotation_adjudication.py`
- `src/thesis3/gt_evaluation.py`
- `src/thesis3/frame_gt_evaluation.py`
- `src/thesis3/gt_eval_suite.py`
- `src/thesis3/gt_eval_report.py`
- `src/thesis3/tracking_gt_evaluation.py`
- `src/thesis3/verification_gt_evaluation.py`
- `src/thesis3/annotation_rules.py`
- `apps/index_mp4_corpus.py`
- `apps/generate_clip_tasks.py`
- `apps/generate_frame_label_tasks.py`
- `apps/build_experiment_manifest.py`
- `apps/export_replay_from_experiment.py`
- `apps/export_annotation_pack.py`
- `apps/bootstrap_camera_setup.py`
- `apps/export_canonical_dataset.py`
- `apps/run_data_audit.py`
- `apps/generate_stress_replay.py`
- `apps/run_method_stress_suite.py`
- `apps/summarize_annotation_queue.py`
- `apps/export_adjudication_tasks.py`
- `apps/evaluate_event_gt.py`
- `apps/evaluate_frame_gt.py`
- `apps/run_gt_eval_suite.py`
- `apps/render_gt_eval_report.py`
- `apps/evaluate_tracking_gt.py`
- `apps/evaluate_verification_gt.py`
- `apps/validate_annotations.py`
- `configs/annotation_vocabulary.template.json`
- `total_log/annotation_gt_playbook.md`

### image-backed baseline

- GT metadata 기반 oracle detector / verifier
- 실제 image_ref를 읽는 mean-intensity detector
- crop variance verifier

관련 경로:
- `src/thesis3/image_io.py`
- `src/thesis3/components.py`
- `configs/scenario_gt_oracle.template.json`
- `configs/scenario_image_stat.template.json`

### live / pseudo-live 입력

- ffmpeg 기반 file-stream / RTSP 입력 어댑터
- grouped live packet 생성
- 기존 scenario pipeline과 연결
- spool frame 저장

관련 경로:
- `src/thesis3/live_stream.py`
- `src/thesis3/live_runtime.py`
- `apps/run_live_stream.py`
- `configs/live_file_stream.template.json`
- `configs/live_rtsp_stream.template.json`

### 교체 실험 구조

- config에서 detector / verifier / tracker 선택 가능
- config에서 trigger policy / candidate selector 선택 가능
- config에서 verification scheduler / confirmation policy 선택 가능
- config에서 safety policy 선택 가능
- environment profile을 config에서 주입 가능
- registry 등록 이름 또는 `module_or_path:Symbol` 형태의 dynamic plugin 로딩 가능
- 여러 config를 한 번에 실행해 비교할 수 있는 suite runner 추가
- 외부 repo용 generic detector / verifier adapter 추가
- custom wrapper template 추가
- detector-only baseline example config 추가
- method-hook example config 추가
- bird-sahi local repo config 추가
- bird-sahi focus suite helper 추가
- bird-sahi operating point sweep helper 추가
- bird-sahi tuned local confirm config / profile 추가
- run_start / readiness / suite summary에 `conda_env`, `python_executable` 기록
- suite summary에 `trigger / verification_schedule / confirmation / verification_failure` reason counter 포함
- bird-sahi keyframe scheduler에 bootstrap / track-local scheduling 옵션 추가
- bird-sahi local confirm 운영점 sweep 결과를 기준으로 `confirm_len=1` tuned operating point 확보

관련 경로:
- `src/thesis3/plugin_loader.py`
- `src/thesis3/external_adapters.py`
- `src/thesis3/methodology.py`
- `src/thesis3/orchestration.py`
- `src/thesis3/runtime.py`
- `src/thesis3/pipelines.py`
- `src/thesis3/safety.py`
- `src/thesis3/suite_runner.py`
- `src/thesis3/readiness.py`
- `src/thesis3/runtime_env.py`
- `apps/run_experiment_suite.py`
- `apps/check_config_readiness.py`
- `apps/run_bird_sahi_focus_suite.py`
- `apps/run_bird_sahi_operating_point_sweep.py`
- `examples/custom_plugins.py`
- `examples/external_repo_models.py`
- `examples/external_repo_wrapper_template.py`
- `configs/scenario_detector_only_baseline.example.json`
- `configs/scenario_methodology_hooks.example.json`
- `configs/scenario_bird_sahi_method_bundle.example.json`
- `configs/scenario_bird_sahi_noconfirm.example.json`
- `configs/scenario_bird_sahi_method_bundle.local.json`
- `configs/scenario_bird_sahi_method_bundle_tuned.local.json`
- `configs/scenario_bird_sahi_noconfirm.local.json`
- `configs/scenario_ccs_lcs_safety_bundle.example.json`
- `configs/scenario_dynamic_plugin.example.json`
- `configs/scenario_b_dynamic_plugin.example.json`
- `configs/scenario_generic_external_wrapper.example.json`
- `configs/scenario_template_external_wrapper.example.json`

## 3. 현재 비어 있는 것

### 실제 모델 연결

- 기존 연구 detector wrapper
- 기존 연구 verifier wrapper 고도화
- 실제 repo output mapping 확정
- 실제 모델별 version/config 추적 규칙
- `bird_sahi_temporal` full verifier-policy bundle fidelity 정리
- `ccs_lcs_project` full policy/safety bundle fidelity 정리
- detector-only baseline을 기준선으로 고정한 suite 비교 규칙
- environment profile별 config layering 규칙
- actual local bird-sahi runtime environment 정리
  - `bird_sahi_new`: `ultralytics` 있음, Python 3.9라서 thesis3 쪽 dataclass compatibility helper를 추가해 실행 가능하게 맞춤
  - `bird_repel`: `ultralytics` 있음, Python 3.9
  - `base`, `lvr-infer`: Python 3.11이지만 `ultralytics` 없음
  - 현재 bird-sahi local 실행 기본 env는 `bird_sahi_new`로 보는 것이 가장 자연스럽다
- 실제 데이터 기준 operating point 재튜닝
  - 현재 local toy replay에서는 `confirm_len=1` tuned confirm이 가장 실용적이다
  - 다만 no-confirm variant는 verification burden과 false accept risk가 더 클 수 있어 실제 데이터에서 다시 확인해야 한다
  - 실제 MP4 / stream 데이터가 오면 review burden, blocked rate, failure taxonomy를 같이 보면서 재조정해야 한다

### 실데이터 적응

- canonical schema 초안 및 export tooling 구현
- camera metadata / calibration bootstrap tooling 구현
- camera inventory 운영형 필드 placeholder 생성
- camera metadata / calibration 실제 source-of-truth 확정
- 실데이터 audit 기준값 / camera-specific heuristics 정리
- 실제 GT 운영 규칙
- annotation vocabulary 실제 현장 기준 확정
- annotator 간 합의가 필요한 ambiguous / unknown 규칙 정리
- adjudication status 운영 규칙과 second-review handoff 절차 고정
- reviewer assignment 규칙과 SLA 성격의 priority rule 정리
- 실제 데이터 기준 stress preset 보정
- 실제 데이터 기준 method stress comparison 해석 규칙 정리

### 운영형 live 시스템 보강

- in-memory frame 전달
- RTSP reconnect
- queue/backpressure 처리
- stream healthcheck
- frame drop 정책

### 평가 확장

- detector / verifier / tracking 정량 평가 스크립트 확장
- GT 기반 precision/recall 자동 계산
- event-level GT 기준 hit/miss/false-alert 계산 초안
- frame-level bbox 기준 precision/recall 계산 초안
- multi-run GT evaluation matrix 초안
- verification accept/reject 기준 GT evaluation 초안
- tracking continuity / id-switch / handoff-success metric 초안
- GT eval suite markdown report 초안
- handoff / tracking / review burden 리포트 확장
- suite 결과 비교 리포트 정리

## 4. 현재 바로 가능한 것

- 샘플 replay 실행
- dynamic plugin config로 detector / trigger policy / candidate selector 교체 실험
- dynamic plugin config로 verification scheduler / confirmation policy 교체 실험
- dynamic plugin config로 safety policy 교체 실험
- generic external detector / verifier adapter로 외부 repo 흉내 모델 연결
- custom wrapper template로 외부 repo wrapper 실험
- detector-only baseline vs method-hook run 비교
- baseline vs bird_sahi verifier-policy bundle vs ccs_lcs safety bundle 비교
- bird_sahi confirmation 포함 / no-confirm variant 비교
- bird_sahi local confirm operating point sweep 실행
- bird_sahi tuned confirm profile과 no-confirm profile을 같은 env에서 재비교
- video asset index에서 canonical sequence export
- replay manifest에서 canonical frame sample export
- video asset index에서 camera inventory / calibration registry template bootstrap
- operational placeholder가 포함된 camera inventory export
- raw MP4 / replay manifest audit JSON 생성
- stress replay preset 생성
- stress manifest에 대해 baseline / bird-sahi / ccs-lcs 비교 실행
- annotation / GT playbook 작성
- annotation vocabulary template 기반으로 GT 규칙 커스터마이즈
- event / frame annotation JSONL에 대해 validator 실행
- unresolved unknown / ambiguous annotation queue 요약
- unresolved annotation을 reviewer handoff task로 export
- event GT와 baseline / method bundle event log를 직접 비교
- frame bbox GT와 detector observation을 직접 비교
- 여러 event log를 같은 GT로 suite 비교
- verification camera GT로 verifier accept/reject를 직접 비교
- tracker_update 로그를 object-id GT와 직접 비교
- GT suite 결과를 markdown report로 렌더링
- MP4를 인덱싱해서 annotation task 만들기
- event GT로 experiment manifest 만들기
- experiment manifest에서 replay bundle 만들기
- pseudo-live file stream으로 scenario A pipeline 태우기
- 여러 config를 suite로 묶어 replay 비교 실행
- config readiness를 먼저 검사해서 실행 전 blocker를 확인
- baseline vs bird-sahi confirm / no-confirm suite를 helper CLI로 바로 비교
- `conda run -n bird_sahi_new ...`로 bird-sahi local config readiness와 suite 실행
- event log summary에서 어떤 env / python으로 실행했는지 바로 확인
- bird-sahi confirm bundle에서 왜 verify가 안 돌았는지, 왜 review로 남았는지를 summary reason counter로 바로 확인

## 5. 다음 단계 핵심

지금 가장 중요한 것은 아래 다섯 가지다.

1. baseline detector-only 비교군과 method variant 비교 규칙 고정
2. `bird_sahi_temporal`을 detector가 아니라 verifier-policy bundle로 번역
3. `ccs_lcs_project`를 safety/policy bundle로 번역
4. 실데이터 canonical schema와 audit 흐름 고정
5. live 경로를 운영형에 가깝게 보강
