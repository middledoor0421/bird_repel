# annotation_gt_playbook

기준일: `2026-04-05`

## 목적

실제 MP4가 들어왔을 때

- 어떤 순서로 annotation을 진행할지
- 어떤 단위의 GT를 만들지
- 어떤 파일을 산출물로 남길지

를 빠르게 복원하기 위한 운영 메모다.

핵심 원칙은 `원본 보존`, `단계적 라벨링`, `negative / hard negative 포함`, `system KPI에 맞는 GT 설계`다.

## 1. 기본 원칙

- raw MP4는 절대 수정하지 않고 read-only로 보존한다.
- 처음부터 모든 프레임 bbox를 만들지 않는다.
- 먼저 event-level GT를 만들고, 그 뒤 필요한 subset만 frame-level bbox로 간다.
- positive만 만들지 말고 negative와 hard negative도 반드시 포함한다.
- split은 frame 단위가 아니라 asset / day / camera / sequence 단위로 나눈다.
- 애매한 경우는 억지로 positive/negative로 밀지 않고 `unknown` 또는 note를 남긴다.

## 2. 권장 GT 단계

### 2-1. event-level GT

목적:
- system KPI
- false alarm / miss 분석
- positive / negative pool 확보

사용 구조:
- [EventAnnotation](/home/middledoor/PycharmProjects/thesis3/src/thesis3/video_data.py)

필수 필드:
- `asset_id`
- `camera_id`
- `start_time_s`
- `end_time_s`
- `label`

권장 태그:
- `blur`
- `glare`
- `night`
- `distant_object`
- `partial_visibility`
- `hard_negative`

### 2-2. frame-level GT

목적:
- detector bbox 평가
- verifier crop 품질 점검

사용 구조:
- [FrameAnnotation](/home/middledoor/PycharmProjects/thesis3/src/thesis3/video_data.py)

언제 만들까:
- representative positive subset
- hard negative subset
- failure case subset

전체 프레임에 대해 만들 필요는 없고, benchmark subset만 정밀하게 만든다.

### 2-3. optional track-level GT

목적:
- handoff
- temporal verification
- track consistency

현재 코드에 전용 schema는 아직 없으므로, 실제 필요가 생기면 event/frame annotation metadata로 임시 기록 후 별도 schema를 추가한다.

## 3. 권장 작업 순서

1. MP4 인덱싱
2. clip task 생성
3. preview pack 생성
4. event-level annotation
5. experiment manifest 생성
6. 필요한 subset만 frame label task 생성
7. frame bbox annotation
8. replay bundle export
9. baseline / method bundle 평가

## 4. 현재 도구와 연결

### MP4 인덱싱

- [index_mp4_corpus.py](/home/middledoor/PycharmProjects/thesis3/apps/index_mp4_corpus.py)

예시:

```bash
python apps/index_mp4_corpus.py \
  --input /path/to/mp4_root \
  --output artifacts/video_assets.jsonl
```

### clip task 생성

- [generate_clip_tasks.py](/home/middledoor/PycharmProjects/thesis3/apps/generate_clip_tasks.py)

### preview pack 생성

- [export_annotation_pack.py](/home/middledoor/PycharmProjects/thesis3/apps/export_annotation_pack.py)

산출물:
- preview mp4
- review html
- event annotation template

### frame-level task 생성

- [generate_frame_label_tasks.py](/home/middledoor/PycharmProjects/thesis3/apps/generate_frame_label_tasks.py)

### experiment manifest 생성

- [build_experiment_manifest.py](/home/middledoor/PycharmProjects/thesis3/apps/build_experiment_manifest.py)

### replay export

- [export_replay_from_experiment.py](/home/middledoor/PycharmProjects/thesis3/apps/export_replay_from_experiment.py)

### event-level 평가

- [evaluate_event_gt.py](/home/middledoor/PycharmProjects/thesis3/apps/evaluate_event_gt.py)

예시:

```bash
python apps/evaluate_event_gt.py \
  --event-log artifacts/scenario_detector_only_baseline/scenario_a-9b2a051a.jsonl \
  --events examples/replay_event_annotations.example.jsonl \
  --output artifacts/evaluation/example_replay_event_eval.json
```

이 평가는 event-level GT 기준으로:
- positive event hit / miss
- negative event clean / false alert
- unmatched alert decision
를 먼저 본다.

### frame-level 평가

- [evaluate_frame_gt.py](/home/middledoor/PycharmProjects/thesis3/apps/evaluate_frame_gt.py)

예시:

```bash
python apps/evaluate_frame_gt.py \
  --event-log artifacts/scenario_gt_oracle/scenario_a-a9c9f370.jsonl \
  --frames examples/replay_frame_annotations_oracle.example.jsonl \
  --output artifacts/evaluation/example_replay_frame_eval.json
```

이 평가는 frame bbox GT 기준으로:
- TP / FN / FP
- precision / recall
- missing detector observation
을 먼저 본다.

### GT eval suite

- [run_gt_eval_suite.py](/home/middledoor/PycharmProjects/thesis3/apps/run_gt_eval_suite.py)

예시:

```bash
python apps/run_gt_eval_suite.py \
  --entry oracle=artifacts/scenario_gt_oracle/scenario_a-a9c9f370.jsonl \
  --events examples/replay_event_annotations_oracle.example.jsonl \
  --frames examples/replay_frame_annotations_oracle.example.jsonl \
  --output artifacts/evaluation/example_gt_eval_suite.json
```

여러 log를 같은 GT로 비교할 때는 이 suite output의 `matrix`를 먼저 본다.

### verification 평가

- [evaluate_verification_gt.py](/home/middledoor/PycharmProjects/thesis3/apps/evaluate_verification_gt.py)

예시:

```bash
python apps/evaluate_verification_gt.py \
  --event-log artifacts/scenario_dynamic_plugin/scenario_a-36a84622.jsonl \
  --frames examples/replay_verification_frame_annotations.example.jsonl \
  --output artifacts/evaluation/example_replay_verification_eval.json
```

이 평가는 verification stage 기준으로:
- true accept
- false accept
- false reject
- true reject
를 먼저 본다.

### tracking / handoff 평가

- [evaluate_tracking_gt.py](/home/middledoor/PycharmProjects/thesis3/apps/evaluate_tracking_gt.py)

예시:

```bash
python apps/evaluate_tracking_gt.py \
  --event-log examples/tracker_handoff_event_log.example.jsonl \
  --frames examples/tracking_frame_annotations_handoff.example.jsonl \
  --output artifacts/evaluation/example_tracking_eval.json
```

이 평가는 tracker 기준으로:
- continuity recall
- object fragmentation
- id switch
- handoff success / failure
를 먼저 본다.

### markdown report

- [render_gt_eval_report.py](/home/middledoor/PycharmProjects/thesis3/apps/render_gt_eval_report.py)

예시:

```bash
python apps/render_gt_eval_report.py \
  --suite-json artifacts/evaluation/example_gt_eval_suite_with_verification.json \
  --output artifacts/evaluation/example_gt_eval_suite_with_verification.md
```

여러 method를 비교할 때는 raw JSON만 보지 말고 markdown report도 같이 남겨두는 편이 낫다.
를 먼저 본다.

### annotation validation

- [validate_annotations.py](/home/middledoor/PycharmProjects/thesis3/apps/validate_annotations.py)
- [annotation_vocabulary.template.json](/home/middledoor/PycharmProjects/thesis3/configs/annotation_vocabulary.template.json)
- [summarize_annotation_queue.py](/home/middledoor/PycharmProjects/thesis3/apps/summarize_annotation_queue.py)
- [export_adjudication_tasks.py](/home/middledoor/PycharmProjects/thesis3/apps/export_adjudication_tasks.py)

예시:

```bash
python apps/validate_annotations.py \
  --events examples/event_annotations.example.jsonl \
  --frames examples/frame_annotations.example.jsonl \
  --video-index examples/annotation_video_assets.example.jsonl \
  --output artifacts/annotations/example_validation.json
```

실제 운영에서는 가능하면 `--video-index`도 같이 넣어서 `asset_id`, `camera_id`, `source_path`, duration consistency까지 같이 점검한다.

`unknown` 또는 second-review 대상이 쌓이기 시작하면 queue summary로 unresolved 규모를 같이 본다.
handoff가 필요해지면 adjudication task export로 reviewer queue JSONL을 만든다.

## 5. annotation 기준

### positive

- 사람이 영상에서 bird 존재를 명확히 확인할 수 있음
- event 구간은 bird가 실제로 보이는 시작/끝 기준으로 잡음

### negative

- bird가 없고, review burden 측정에 포함해도 되는 일반 배경 구간

### hard negative

- bird는 없지만 detector / verifier가 헷갈릴 만한 구간
- 예: 반사, 조명, 먼 물체, 복잡한 배경, 작은 움직임

### unknown

- 너무 멀거나 흐려서 annotator가 확신할 수 없음
- quality issue 분석용으로 분리
- 가능하면 `metadata.ambiguity_reasons`를 같이 남긴다
- 가능하면 `metadata.adjudication_status`를 같이 남긴다

권장 `ambiguity_reasons` 예시:
- `too_small`
- `too_blurry`
- `severe_glare`
- `occluded`
- `distant_motion`
- `uncertain_species`
- `conflicting_cues`
- `insufficient_context`

권장 `adjudication_status` 예시:
- `pending`
- `needs_second_review`
- `resolved`
- `waived`

권장 운영 흐름:
1. 1차 annotator가 확신이 없으면 `label=unknown`, `adjudication_status=pending`
2. 1차 self-check 후도 애매하면 `needs_second_review`로 올림
3. 2차 reviewer가 최종 label을 정하면 `resolved`
4. 학습/평가에서 제외하기로 합의한 경우 `waived`

## 6. sampling 전략

- 전체 데이터에는 event-level GT 우선
- positive subset에는 frame-level bbox 일부 추가
- hard negative subset도 frame-level 일부 추가
- 초기에는 failure-driven sampling을 우선
- baseline 결과를 본 뒤 miss / false alarm이 잦은 유형을 더 라벨링

## 7. quality / metadata 규칙

annotation 때 가능하면 같이 남길 것:

- `quality_tags`
- `bird_count_min`, `bird_count_max`
- `notes`
- `annotator`
- `metadata.ambiguity_reasons`
- `metadata.adjudication_status`

camera / environment 차이는 annotation 파일보다 inventory 쪽에서 관리한다.

관련:
- [camera_inventory.py](/home/middledoor/PycharmProjects/thesis3/src/thesis3/camera_inventory.py)
- [canonical_data.py](/home/middledoor/PycharmProjects/thesis3/src/thesis3/canonical_data.py)

## 8. split 규칙

- 같은 asset의 인접 구간은 서로 다른 split으로 찢지 않는다.
- 같은 날 / 같은 카메라 / 같은 상황이 train/val/test에 동시에 퍼지지 않게 주의한다.
- detector 평가용 split과 system replay용 split이 다를 수 있음을 기록한다.

## 9. QA 체크리스트

- label이 없는 asset이 섞이지 않았는가
- positive만 과도하게 많은 것은 아닌가
- hard negative가 충분히 포함되었는가
- bbox가 너무 타이트하거나 너무 느슨하지 않은가
- split leakage 위험이 없는가
- replay export 후 sample label과 GT가 일치하는가
- event / frame annotation JSONL이 validator를 통과하는가
- custom vocabulary를 쓴 경우 template 대비 어떤 값이 추가되었는지 기록했는가
- unresolved unknown / ambiguous annotation 수가 관리 가능한 수준인지 queue summary로 확인했는가

## 10. adjudication handoff

reviewer에게 넘길 unresolved 건은 JSONL task로 뽑아두는 편이 낫다.

예시:

```bash
python apps/export_adjudication_tasks.py \
  --events examples/event_annotations_unknown.example.jsonl \
  --frames examples/frame_annotations_unknown.example.jsonl \
  --output-tasks artifacts/annotations/example_adjudication_tasks.jsonl \
  --output-summary artifacts/annotations/example_adjudication_task_summary.json
```

이 task에는 다음이 들어간다:
- 어떤 annotation을 다시 봐야 하는지
- event인지 frame인지
- 현재 `adjudication_status`
- `primary_review`인지 `second_review`인지
- 누가 받는 게 자연스러운지 (`primary_annotator` / `secondary_reviewer`)
- ambiguity reason과 priority

## 11. 실데이터 도착 직후 추천 루틴

1. MP4 index 생성
2. camera inventory / calibration registry 초안 생성
3. data audit 실행
4. clip task + preview pack 생성
5. event-level GT부터 시작
6. detector-only baseline replay 실행
7. failure case를 보고 frame-level bbox subset 선정
