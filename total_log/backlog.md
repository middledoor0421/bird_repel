# backlog

기준일: `2026-04-05`

## 현재 상태

- 현재는 `실데이터 도착 전 대기` 상태다.
- 아래 backlog는 "지금 당장 모두 진행"이라기보다, `실데이터가 도착하면 바로 이어서 할 작업` 중심으로 유지한다.

## 재개 조건

- 실제 MP4 또는 live stream 첫 배치 수령
- camera inventory를 실제 값으로 채울 수 있는 site / device metadata 수령
- annotator 운영 방식 또는 GT 작성 범위에 대한 최소 결정

## P0. 바로 해야 할 것

### 1. baseline과 방법론 번들 비교 규칙 고정

- detector-only baseline config를 기준선으로 유지
- method variant 실행 시 어떤 훅이 바뀌었는지 로그에 남기기
- suite 결과에서 baseline 대비 차이를 바로 볼 수 있게 규칙 정리

완료 조건:
- baseline detector-only vs method variant를 항상 같은 입력에서 비교 가능

### 2. 기존 연구 모델 wrapper 연결

- detector wrapper 초안 작성
- verifier wrapper 초안 작성
- 모델 경로 / config / version naming 규칙 정리
- 동일 입력에서 기존 코드와 새 wrapper 출력 비교
- `bird_sahi_temporal`은 verifier-policy bundle로 연결
- `ccs-lcs`는 safety/policy bundle로 연결
- bundle별 example config와 template config 유지
- 실행 전 readiness check를 통과하는 실제 runtime 환경까지 준비
- method별 권장 conda env와 Python 버전 제약 정리

완료 조건:
- 현재 plugin interface로 실제 detector/verifier를 선택해 실행 가능

### 3. 실데이터 수용 schema 고정

- raw mp4 / stream 메타데이터 필드 정리
- camera_id / timestamp / calibration / environment tag 구조 정리
- canonical schema 초안 작성
- raw -> canonical 변환 스크립트 설계
- current draft tooling:
  - `apps/export_canonical_dataset.py`
  - `apps/bootstrap_camera_setup.py`
  - `src/thesis3/canonical_data.py`
  - `src/thesis3/camera_inventory.py`
- 남은 일:
  - 실제 카메라 메타데이터 기준으로 필드 확정
  - calibration_ref / environment_tag source-of-truth 결정
  - `installation_id`, `safe_zone_ref`, `stream_uri_ref`의 실제 관리 위치 확정
  - `mount_height_m`, `view_direction_deg` 입력 규칙과 측정 단위 고정
  - frame sample과 sequence record 간 join 규칙 확정

완료 조건:
- 실데이터를 받자마자 어디에 어떻게 저장할지 정해져 있음

### 4. data audit 도구 준비

- fps / duration / resolution / codec 점검
- blur / brightness / glare 같은 quality 통계 초안
- object size / positive event 분포 요약 틀
- current draft tooling:
  - `apps/run_data_audit.py`
  - `src/thesis3/data_audit.py`
- 남은 일:
  - 실제 데이터 기준 quality threshold / warning rule 보정
  - glare / day-night / annotation feasibility 같은 domain-specific 항목 추가
  - camera별 audit summary 템플릿 고정

완료 조건:
- 실데이터 첫 배치가 오면 바로 audit 가능

## P1. 실험 가능한 baseline 강화

### 5. 교체 실험 규칙 정리

- dynamic plugin 사용 규칙 문서화
- config naming convention 정리
- suite 결과 비교 기준 정리
- environment profile layering 규칙 정리
- verification scheduler / confirmation policy naming 규칙 정리
- bird-sahi focus suite와 같은 method별 비교 preset 정리
- method별 reason counter를 보고 threshold / interval / confirmation을 조정하는 운영 규칙 정리
- bird-sahi tuned confirm operating point를 demo toy replay가 아니라 실제 MP4 / GT replay 기준으로 다시 고정
- no-confirm variant는 upper-bound reference로 남기고, review burden 대비 false accept risk를 실제 데이터에서 따로 검토
- stress preset 비교는 현재 `apps/run_method_stress_suite.py`로 가능
- stress profile별 승패보다 failure mode 차이를 해석하는 규칙 정리

완료 조건:
- 다른 팀 모델을 최소 수정으로 붙이고 동일 입력에서 비교 가능

### 6. GT 기반 정량 평가 확장

- event-level KPI
- frame-level detector KPI
- verification KPI
- positive / negative / hard negative 분리 평가
- current draft tooling:
  - `apps/evaluate_event_gt.py`
  - `src/thesis3/gt_evaluation.py`
  - `apps/evaluate_frame_gt.py`
  - `src/thesis3/frame_gt_evaluation.py`
  - `apps/run_gt_eval_suite.py`
  - `apps/evaluate_verification_gt.py`
  - `src/thesis3/verification_gt_evaluation.py`
  - `apps/evaluate_tracking_gt.py`
  - `src/thesis3/tracking_gt_evaluation.py`
  - `apps/render_gt_eval_report.py`
- 남은 일:
  - frame-level bbox 기준 detector metric 추가
  - verifier acceptance / rejection를 GT와 연결하는 metric 추가
  - event-level evaluator를 suite 결과 비교와 연결
  - frame-level evaluator를 suite 결과 비교와 연결한 뒤 method별 report format 고정
  - verification evaluator를 suite 결과 비교와 연결한 뒤 operating point report format 고정
  - tracking/handoff evaluator를 실제 multi-camera replay 기준으로 보정
  - markdown report를 method comparison narrative와 risk summary까지 확장
  - positive action state definition을 운영 목적별로 분리

### 7. scenario A baseline 구체화

- trigger policy plugin 개선
- verification request 정책 plugin 구체화
- confirmation / scheduling plugin 구체화
- stage1-stage2 handoff 메타데이터 정리

### 8. MP4 annotation workflow 보강

- preview pack 태그 규칙 정리
- event annotation quality rule 정리
- frame annotation subset sampling 정책 정리
- current draft playbook:
  - `total_log/annotation_gt_playbook.md`
- current draft tooling:
  - `apps/validate_annotations.py`
  - `src/thesis3/annotation_rules.py`
  - `configs/annotation_vocabulary.template.json`
- 남은 일:
  - 실제 annotator workflow 기준으로 label vocabulary 확정
  - site / camera 환경별 custom vocabulary 분리 규칙 정리
  - unknown / ambiguous case adjudication 규칙 정리
  - `pending` / `needs_second_review` / `resolved` 운영 기준과 담당자 handoff 정리
  - reviewer assignment rule과 priority/SLA 기준 정리
  - asset index와 결합한 validation을 실제 annotation handoff 절차에 포함
  - track-level GT가 필요한지 실제 failure 분석 후 결정

### 9. synthetic stress preset 보강

- `sync_jitter`, `quality_drop`, `camera_dropout`, `latency_spike`, `mixed_faults` preset을 실제 환경 기준으로 보정
- bbox noise / timestamp drift / camera dropout을 scenario A/B별로 더 현실적으로 나누기
- stress replay를 baseline / bird-sahi / ccs-lcs 비교 suite에 연결

## P2. 운영형 live 시스템 보강

### 10. live 입력 경로 개선

- disk spool 최소화 또는 제거
- in-memory frame 전달 구조 검토
- RTSP reconnect / timeout 처리
- source healthcheck 추가

### 11. queue / backpressure 관리

- frame backlog 측정
- frame skip 정책
- verification budget 관리

### 12. observability 보강

- camera별 ingest FPS
- decoder latency
- queue depth
- dropped frame count

## P3. 연구 문제로 이어질 항목

### 13. handoff 안정성 연구

- projected ROI
- re-acquisition rate
- handoff latency

### 14. temporal / multi-view verification

- single-frame vs multi-frame verifier 비교
- quality-aware gating
- uncertainty / reject option

### 15. active learning / annotation 효율

- hard negative 우선 라벨링
- disagreement 기반 샘플 선택
- failure mining 자동화

## 보류 또는 나중

- 실제 hardware adapter
- 실제 action interface
- shadow mode 이후 물리 연동
