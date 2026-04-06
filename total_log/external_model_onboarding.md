# external_model_onboarding

기준일: `2026-04-04`

## 목적

외부 detector / verifier / safety 모듈을 `thesis3` 시스템에 붙일 때
"어느 repo를 어떤 방식으로 연결해야 하는지"를 빠르게 복원하기 위한 메모다.

## 현재 확인한 후보 repo

### 1. `bird_repel`

관련 경로:
- `../bird_repel/central/detector/model.py`

핵심 구조:
- `BirdDetector(weights, device, input_size, conf_th, iou_th, only_bird=True)`
- `infer(image_bgr) -> List[Detection]`
- 각 `Detection`은 `box=(x, y, w, h)`, `conf`

현재 연결 상태:
- `thesis3` 쪽에 `bird_repel_detector` wrapper 추가 완료
- 관련 구현:
  - `src/thesis3/research_repo_adapters.py`
  - `configs/scenario_bird_repel_detector.template.json`
  - `configs/scenario_bird_repel_detector.example.json`

권장 사용:
- 실제 repo 연결 시 detector stage1 후보
- 입력은 기본적으로 `numpy_bgr`
- YOLO weights 경로와 device만 정하면 바로 붙일 수 있는 형태

### 2. `bird_sahi_temporal`

관련 경로:
- `../bird_sahi_temporal/detector/yolo_wrapper.py`

핵심 구조:
- `YoloDetector(weights, device='cuda:0', img_size=640, conf_thres=0.25, class_mapping=None)`
- `predict(frame) -> (boxes_xyxy, scores, labels)`
- boxes는 `xyxy`, scores는 float array, labels는 int array

연구 관점 해석:
- 이 프로젝트의 중심은 `detector 자체`보다 `yolo_plus_local_verifier` 구조다
- 즉 `wide-area YOLO detector + local verifier + verification scheduling policy`가 핵심이다
- `always_verify`, `keyframe_verify`, `temporal_sahi_v7`, `crop_recheck`, `confirmation`이 모두 이 축에 속한다
- 문서 기준 핵심 메시지도 `verification invocation policy`에 있다

현재 연결 상태:
- `thesis3` 쪽에 `bird_sahi_temporal_yolo_detector` wrapper 추가 완료
- `bird_sahi_temporal_local_verifier`도 추가해서 local crop recheck verifier backend를 꽂을 수 있게 함
- `bird_sahi_always_verify_scheduler`, `bird_sahi_keyframe_verify_scheduler`, `bird_sahi_confirmation_policy`도 추가해서 `verify schedule + confirmation`을 method 이름으로 붙일 수 있게 함
- 다만 full temporal SAHI 전체를 그대로 옮긴 것은 아니고, 여전히 dual-budget / targeted verification 같은 policy-level 요소는 이후 단계다
- 관련 구현:
  - `src/thesis3/research_repo_adapters.py`
  - `configs/scenario_bird_sahi_detector.template.json`
  - `configs/scenario_bird_sahi_detector.example.json`
  - `configs/scenario_bird_sahi_method_bundle.template.json`
  - `configs/scenario_bird_sahi_method_bundle.example.json`
  - `configs/scenario_bird_sahi_noconfirm.template.json`
  - `configs/scenario_bird_sahi_noconfirm.example.json`
  - `configs/scenario_bird_sahi_method_bundle.local.json`
  - `configs/scenario_bird_sahi_noconfirm.local.json`

권장 사용:
- detector 입구만 빠르게 재사용할 때는 stage1 detector 후보
- 연구 내용 자체를 반영할 때는 `local verifier + verification scheduler + confirmation policy` 조합으로 쓰는 것이 맞다
- 현재 `thesis3`에서 바로 비교 가능한 bird-sahi 쪽 operating style은
  - confirmation 포함 bundle
  - no-confirm partial approximation
  두 가지다
- 로컬 repo에서 바로 시작할 수 있도록 `../bird_sahi_temporal/weights/yolov8n.pt`,
  `../bird_sahi_temporal/configs/coco_bird_only_class_mapping.json`를 박아둔 local config도 추가했다
- 현재 이 머신의 기본 `python`과 `lvr-infer` 환경에는 `ultralytics`가 없어서 실제 YOLO inference는 아직 불가하다
  단, wrapper는 lazy-load로 바꿔서 구조 검증과 config 검증은 계속 가능하다
- 이제 `apps/check_config_readiness.py`로 local config readiness를 바로 확인할 수 있고,
  `bird_sahi_new` env에서는 local config readiness가 정상 통과한다
- `apps/run_bird_sahi_focus_suite.py`로 baseline / bird-sahi confirm / bird-sahi no-confirm 비교를
  demo profile 또는 local profile 기준으로 바로 실행할 수 있다
- 기존 env 조사 결과:
  - `bird_sahi_new`: `ultralytics 8.3.235`, Python 3.9
  - `bird_repel`: `ultralytics 8.3.235`, Python 3.9
  - `base`: Python 3.11, `ultralytics` 없음
  - `lvr-infer`: Python 3.11, `ultralytics` 없음
- thesis3 쪽에 Python 3.9용 dataclass compatibility helper를 넣어서
  `bird_sahi_new`에서도 현재 코드를 직접 실행할 수 있게 맞췄다
- local confirm config는 짧은 replay에서도 confirm path를 실제로 태워보기 위해
  `bootstrap_first_n=2`, `use_track_local_index=true`를 사용한다
- suite summary에는 이제 `trigger_reasons`, `verification_schedule_reasons`,
  `confirmation_reasons`, `verification_failure_reasons`가 같이 들어가서
  왜 verify가 호출됐는지, 왜 pending/reject가 났는지 바로 볼 수 있다
- `apps/run_bird_sahi_operating_point_sweep.py`로 local confirm operating point를 자동 sweep할 수 있다
- small local sweep 기준으로는 threshold보다 `confirm_len` 영향이 컸고,
  `confirm_len=1` 계열이 `confirm_len=2` 계열보다 review burden이 낮았다
- 이를 바탕으로 `configs/scenario_bird_sahi_method_bundle_tuned.local.json`을 추가했고,
  `apps/run_bird_sahi_focus_suite.py --profile local_tuned`로 baseline / tuned confirm / no-confirm을 다시 비교할 수 있다
- 현재 toy replay 기준 추천 출발점은
  - baseline: detector-only fixed comparison
  - confirm variant: `scenario_bird_sahi_method_bundle_tuned.local.json`
  - aggressive reference: `scenario_bird_sahi_noconfirm.local.json`
- local tuned confirm 결과는 `SIMULATED_ACTION 3 / REVIEW_REQUIRED 1`, verification request 3건이고,
  no-confirm은 `SIMULATED_ACTION 3 / BLOCKED 1`, verification request 4건이다
- 따라서 현시점에서는 no-confirm을 바로 기본값으로 쓰기보다,
  tuned confirm을 초기 operating point로 두고 실제 데이터에서 다시 조정하는 편이 자연스럽다
- 입력은 기본적으로 `numpy_rgb`
- label id를 class name으로 바꾸려면 `class_name_map` 사용

### 3. `ccs_lcs_project`

관련 경로:
- `../ccs_lcs_project/lcs/simple_lcs.py`
- `../ccs_lcs_project/lcs/simple_lcs_v2.py`
- `../ccs_lcs_project/system_eval/types.py`

핵심 구조:
- `SimpleLCS.verify(trig, ctx, lcs_score) -> LCSDecision`
- `SimpleLCSV2.verify(trig, ctx, lcs_score, state) -> LCSDecision`

판단:
- 이것은 일반적인 `verifier`보다 `safety/policy gate`에 더 가깝다
- 현재 `thesis3`의 verifier slot에 억지로 넣는 것보다
  policy adapter 또는 safety module로 분리하는 편이 구조상 맞다

현재 상태:
- `thesis3` 쪽에 `ccs_lcs_safety_policy` 추가 완료
- full repo 코드를 직접 import한 것은 아니고, 동일한 역할의 safety/policy slot으로 번역한 상태다
- 관련 구현:
  - `src/thesis3/safety.py`
  - `configs/scenario_ccs_lcs_safety_bundle.template.json`
  - `configs/scenario_ccs_lcs_safety_bundle.example.json`

## 현재 추천 경로

1. detector는 `bird_repel` 또는 `bird_sahi_temporal` 중 하나를 먼저 실제 weights와 함께 연결
2. `bird_sahi_temporal`은 detector가 아니라 verifier-policy bundle로 보는 것이 맞다
3. verifier는 generic/template wrapper로 기존 연구 코드를 별도 연결
4. `ccs_lcs_project`는 verifier가 아니라 `policy/safety adapter`로 별도 연결

## 바로 쓸 수 있는 구현

### generic adapter

관련:
- `src/thesis3/external_adapters.py`
- `configs/scenario_generic_external_wrapper.example.json`

적합한 경우:
- 외부 모델이 dict/list 중심 출력이고 포맷이 단순할 때

### custom template wrapper

관련:
- `examples/external_repo_wrapper_template.py`
- `configs/scenario_template_external_wrapper.example.json`

적합한 경우:
- 외부 모델의 입력/출력 포맷이 특이해서 generic adapter로 안 맞을 때

### repo-specific detector wrapper

관련:
- `src/thesis3/research_repo_adapters.py`

현재 제공:
- `bird_repel_detector`
- `bird_sahi_temporal_yolo_detector`

### repo-specific method bundle pieces

관련:
- `src/thesis3/research_repo_adapters.py`
- `src/thesis3/safety.py`

현재 제공:
- `bird_sahi_temporal_local_verifier`
- `bird_sahi_always_verify_scheduler`
- `bird_sahi_keyframe_verify_scheduler`
- `bird_sahi_confirmation_policy`
- `ccs_lcs_safety_policy`

## 다음 실제 작업 추천

1. 실제 detector-only baseline config를 기준선으로 고정
2. local config 또는 template config에서 device를 실제 환경에 맞게 조정
3. `conda run -n bird_sahi_new python apps/check_config_readiness.py --config configs/scenario_bird_sahi_method_bundle.local.json --config configs/scenario_bird_sahi_noconfirm.local.json`로 local readiness를 먼저 확인
4. `conda run -n bird_sahi_new python apps/run_bird_sahi_focus_suite.py --profile local`로 baseline / bird_sahi variants 비교
5. 필요하면 `conda run -n bird_sahi_new python apps/run_bird_sahi_operating_point_sweep.py --include-noconfirm --output-dir artifacts/sweeps/bird_sahi_local_small_sweep`로 confirm operating point를 sweep
6. 현재는 `conda run -n bird_sahi_new python apps/run_bird_sahi_focus_suite.py --profile local_tuned` 결과를 초기 operating point 후보로 보고,
   suite summary의 reason counter를 보면서 실제 MP4 / GT replay에 맞게 `interval`, `bootstrap_first_n`, `score_threshold`, `confirm_len`을 다시 조정
