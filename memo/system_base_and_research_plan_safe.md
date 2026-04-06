# 실데이터 기반 임시 검증 플랫폼 설계 및 이후 연구 계획

## 문서 목적
이 문서는 실제 측정 데이터가 도착하기 전후에 사용할 **임시 검증 플랫폼**과, 이후 실제 시스템 구현으로 연결하기 위한 **연구 및 실험 방향**을 정리한 것이다.  
다만 요청 내용에는 탐지-검증-물리 장치 작동 판단까지 포함될 수 있으므로, 이 문서는 **고위험 물리 장치의 자율 작동 로직은 제외**하고, 다음 범위에 한정한다.

- 다중 카메라 기반 객체 탐지/검증 파이프라인
- 트리거 전달, 재관측, 추적 유지, 상태 관리
- 실데이터 기반 검증용 소프트웨어 베이스
- 로그, 재현성, 실패 분석, 성능 측정
- 모의 액추에이터(simulator) 또는 안전 게이트(human approval / software interlock) 기반 테스트

즉, 목표는 실제 구현 전 단계에서 **실데이터를 흘려 넣었을 때 시스템이 끝까지 안정적으로 동작하는지 검증 가능한 코드 베이스**를 만드는 것이다.

---

## 1. 현재 상황 요약

### 1.1 일정과 목적
- 실제 측정 데이터는 곧 유입될 예정
- 실제 시스템 구현은 데이터 확보 후 약 한 달 뒤에 가능
- 그 전까지는 실제 측정 데이터를 사용하되, 물리 시스템 완성본이 아니라 **실제 구현과 유사한 소프트웨어 플랫폼**을 먼저 구축해 반복 테스트 필요

### 1.2 현재 고려 중인 두 실험 시나리오

#### 시나리오 A: 2-stage camera-verification pipeline
- Central camera system이 넓은 시야에서 객체를 탐지
- 탐지 결과를 기반으로 trigger event를 생성
- 2차 카메라 시스템(예: laser camera 또는 고배율 검증 카메라)이 해당 객체를 재관측하여 검증
- 검증 결과를 바탕으로 **안전 게이트**를 통과한 경우에만 이후 장치 인터페이스를 호출하거나 모의 액추에이터를 구동

#### 시나리오 B: multi-zoom single-pipeline validation system
- 기존 single-stage 구조를 기반으로 하되, 다양한 zoom/FOV를 가진 카메라를 활용
- wide view에서 후보를 찾고, medium/tele view에서 재검증
- 기존 연구에서 사용한 small-object verifier를 통합하여 작은 객체의 오탐/누락을 줄이는 구조

### 1.3 모델 구성 전제
- 현재는 기본 detector를 사용
- 이후 다른 연구자가 개발하는 전용 detector를 plugin 형태로 합류 가능하도록 설계 필요
- verifier는 기존 연구 성과를 재사용하되, 코드 구조는 시스템형으로 재작성 필요

---

## 2. 왜 기존 논문 코드를 그대로 쓰면 위험한가

논문용 코드는 보통 다음 특성을 가진다.

- 단일 실험 목적에 최적화됨
- 입력 형식이 이미 정리되어 있다는 가정이 많음
- 실패 케이스 처리보다 평균 성능 확인에 집중함
- notebook/script 중심이라 재현성과 상태 관리가 약함
- 카메라 간 handoff, timestamp mismatch, frame drop, calibration drift 같은 시스템 이슈를 다루지 않음

반면 지금 필요한 것은 다음이다.

- 실데이터의 불완전성, 누락, 지연을 견디는 구조
- detector/verifier/tracker를 바꿔 끼울 수 있는 인터페이스
- 실제 장비가 붙기 전에도 동일한 흐름을 흉내 낼 수 있는 simulator layer
- 실패를 숨기지 않고 기록하는 logging/monitoring 체계

따라서 전략은 명확하다.

1. 기존 논문 코드는 **reference implementation**으로 보존한다.
2. 실제 검증 플랫폼은 **새로운 시스템 코드 베이스**로 만든다.
3. 기존 detector/verifier의 핵심 로직만 모듈화해서 이식한다.

---

## 3. 전체 시스템 베이스 구현 방향

## 3.1 핵심 원칙

### 원칙 1. 모델보다 인터페이스를 먼저 고정한다
처음에는 detector 성능보다도, 다음이 먼저 고정되어야 한다.

- 입력 frame/event 형식
- detection output schema
- verification request/result schema
- tracking state schema
- decision/log schema

이 인터페이스가 고정되어야 detector가 바뀌거나 verifier가 바뀌어도 시스템 전체가 흔들리지 않는다.

### 원칙 2. config-driven 구조로 만든다
하드코딩된 threshold, camera 조합, verifier on/off는 나중에 모두 병목이 된다.  
YAML/JSON 기반 설정 파일로 다음을 전부 바꾸게 해야 한다.

- camera source 목록
- 각 카메라의 intrinsic/extrinsic metadata
- detector/verifier 모델 경로
- confidence threshold
- trigger 정책
- tracking timeout
- verification budget
- experiment tag

### 원칙 3. 실제 장치 대신 mock/simulator를 먼저 붙인다
실제 장치 제어를 바로 붙이지 말고, 우선은 아래 단계로 간다.

- Stage 1: detection/verification 결과를 file/db로 저장
- Stage 2: 모의 액추에이터가 decision event를 수신하고 성공/실패를 흉내 냄
- Stage 3: 실제 하드웨어 인터페이스는 별도 adapter로 교체

이렇게 해야 perception stack과 hardware stack을 분리해서 검증할 수 있다.

### 원칙 4. 모든 결과는 재생산 가능해야 한다
실험 재현을 위해 최소한 다음이 저장되어야 한다.

- raw input reference
- synchronized timestamp
- camera id
- model version
- preprocess version
- config hash
- detector output
- verifier output
- final decision state
- error / warning logs

---

## 3.2 권장 소프트웨어 구조

```text
project_root/
  apps/
    run_offline_replay.py
    run_live_mock.py
    evaluate_run.py
  configs/
    scenario_a.yaml
    scenario_b.yaml
    models/
    cameras/
  src/
    core/
      types/
      config/
      registry/
      logging/
      time_sync/
    io/
      readers/
      writers/
      dataset_adapters/
    sensors/
      camera_interfaces/
      calibration/
      synchronization/
    perception/
      detectors/
      verifiers/
      preprocess/
      postprocess/
      tracking/
      association/
    pipeline/
      scenario_a/
      scenario_b/
      shared/
    decision/
      policy_gate/
      confidence/
      uncertainty/
      safety_gate/
    simulators/
      trigger_simulator/
      actuator_simulator/
      delay_fault_simulator/
    storage/
      event_store/
      prediction_store/
      artifact_store/
    evaluation/
      metrics/
      failure_analysis/
      report/
    ops/
      monitoring/
      healthcheck/
      profiling/
  tests/
    unit/
    integration/
    replay/
  docs/
```

### 구조 해설
- `apps/`: 실행 진입점
- `core/`: 타입, 설정, 공통 로깅, 시간 동기화
- `io/`: 실데이터 입력 어댑터
- `sensors/`: 카메라 메타데이터, calibration, sync
- `perception/`: detector/verifier/tracker 등 핵심 AI 모듈
- `pipeline/`: 시나리오별 흐름 정의
- `decision/`: confidence, uncertainty, policy gate
- `simulators/`: 실제 장치 없이 end-to-end를 검증하기 위한 모의 계층
- `storage/`: 결과 및 로그 저장
- `evaluation/`: 성능 지표, 실패 분석, 보고서 자동화

---

## 3.3 공통 데이터 구조

아래 객체들을 공통 타입으로 정의하는 것이 중요하다.

### FramePacket
- `frame_id`
- `camera_id`
- `timestamp`
- `image_ref`
- `exposure / gain / zoom / focal metadata`
- `sync_status`

### DetectionCandidate
- `candidate_id`
- `frame_id`
- `bbox / mask / point`
- `class_name`
- `detector_confidence`
- `detector_version`
- `feature_embedding(optional)`

### TrackState
- `track_id`
- `linked_candidate_ids`
- `start_time / last_seen_time`
- `camera_history`
- `state` (new / tentative / confirmed / lost)
- `track_confidence`

### VerificationRequest
- `request_id`
- `source_track_id`
- `source_camera_id`
- `target_camera_id`
- `roi_hint`
- `trigger_reason`
- `deadline_ms`

### VerificationResult
- `request_id`
- `verified`
- `verifier_score`
- `verifier_version`
- `supporting_bbox`
- `quality_score`
- `failure_reason`

### DecisionRecord
- `track_id`
- `stage1_summary`
- `stage2_summary`
- `policy_state`
- `action_state`
- `human_review_required`
- `timestamp`

여기서 중요한 것은 `action_state`를 바로 고위험 물리 작동과 연결하지 말고, 다음처럼 추상화하는 것이다.

- `NO_ACTION`
- `REVIEW_REQUIRED`
- `SIMULATED_ACTION`
- `BLOCKED_BY_SAFETY_GATE`

---

## 3.4 시나리오 A: 2-stage 시스템용 베이스 파이프라인

## 3.4.1 목표
넓은 시야의 central camera에서 후보를 포착하고, 2차 관측 카메라가 재확인하는 구조를 소프트웨어적으로 안정화하는 것.

## 3.4.2 처리 흐름
1. Central camera frame 수신
2. Stage-1 detector 수행
3. 후보 객체 생성
4. tracker가 temporal consistency 확인
5. trigger policy가 재관측 필요 여부 판단
6. verification request 생성
7. Stage-2 camera frame 또는 ROI 수신
8. verifier 수행
9. verifier score + 품질 점수 + track history 결합
10. policy gate가 최종 상태 결정
11. 실제 장치 대신 actuator simulator 또는 review queue에 전달
12. 전 과정 저장

## 3.4.3 이 구조에서 필요한 핵심 모듈

### A. Trigger policy
단순 confidence 임계값만으로는 부족하다. 다음을 함께 고려해야 한다.

- detector confidence
- object size
- track persistence
- camera overlap region
- stage2 camera availability
- latency budget
- image quality

### B. Handoff manager
central camera에서 잡힌 후보를 stage2 camera가 볼 수 있는 좌표계 또는 ROI로 넘겨야 한다.  
실제 구현 전이라도 다음을 먼저 분리해 둬야 한다.

- camera-to-camera mapping
- ROI projection
- timestamp alignment
- handoff timeout

### C. Verification combiner
검증 결과는 단일 score로만 보지 말고 다음을 함께 본다.

- verifier score
- track length
- stage1-stage2 consistency
- quality score
- motion consistency

### D. Safety/policy gate
고위험 장치가 있다면 여기는 반드시 perception과 분리되어야 한다.  
현재 임시 플랫폼에서는 다음 형태만 사용한다.

- accept for simulated action
- send to manual review
- reject
- block due to low quality / timeout / OOD

---

## 3.5 시나리오 B: multi-zoom 단일 파이프라인 베이스

## 3.5.1 목표
wide/medium/tele zoom camera를 활용해 단일 파이프라인 내에서 후보 탐지와 재검증을 수행하고, 작은 객체에 대한 verifier 효과를 체계적으로 측정하는 것.

## 3.5.2 처리 흐름
1. wide view에서 detector가 후보를 탐지
2. candidate ranking 수행
3. zoom scheduler가 어느 카메라 또는 어느 zoom 레벨로 재관측할지 결정
4. verifier가 작은 객체에 대해 재검증
5. tracker가 서로 다른 zoom view 간 identity를 유지
6. policy gate가 상태 결정
7. 결과를 simulator/logging에 전달

## 3.5.3 핵심 연구 포인트

### A. Zoom scheduling policy
어떤 후보에 더 큰 배율을 할당할 것인가가 중요하다.

가능한 기준:
- detector confidence가 애매한 경우
- object size가 너무 작은 경우
- false positive가 잦은 class인 경우
- 이미 일정 시간 이상 지속 관측된 track인 경우

### B. Multi-view identity consistency
zoom이 바뀌면 같은 물체인지 연결이 어렵다.  
따라서 tracking/association이 verifier 못지않게 중요하다.

### C. Verification cost control
모든 후보를 고배율로 확인하면 계산량과 latency가 커진다.  
그래서 top-k candidate, confidence band, track duration 기반으로 verification budget을 관리해야 한다.

---

## 3.6 detector / verifier / tracker plugin 설계

향후 다른 연구자의 detector가 합류하는 점을 고려하면, 모델 자체보다 **표준 인터페이스**가 중요하다.

### Detector interface
입력:
- image 또는 frame packet
- optional ROI / camera metadata

출력:
- detection candidate list
- latency
- internal diagnostics(optional)

### Verifier interface
입력:
- cropped patch 또는 ROI sequence
- source metadata
- optional context features

출력:
- verified boolean 또는 score
- quality estimate
- uncertainty(optional)
- failure reason(optional)

### Tracker interface
입력:
- detection list
- timestamp
- camera metadata

출력:
- updated tracks
- association result
- lost/new tracks

### 설계 원칙
- detector와 verifier는 서로 직접 참조하지 않는다.
- pipeline이 둘을 orchestration 한다.
- 각 모듈은 version string을 반드시 출력한다.
- 실행 결과는 모두 동일한 schema로 저장한다.

---

## 3.7 기존 논문 코드에서 무엇을 가져오고 무엇을 버릴지

## 3.7.1 가져올 것
- 기존 verifier 모델 구조와 weight
- small-object 처리 아이디어
- detector 후처리 방식 중 재사용 가치가 있는 부분
- 논문에서 검증된 feature extractor / scoring logic
- 기존 evaluation code 중 지표 산출 부분

## 3.7.2 그대로 쓰면 안 되는 것
- notebook 기반 데이터 입출력
- 실험마다 바뀐 경로 하드코딩
- stage별 상태가 암묵적으로 이어지는 코드
- exception을 무시하고 넘어가는 부분
- 논문용 static split 가정
- 단일 카메라, 단일 timestamp 가정

## 3.7.3 마이그레이션 전략
1. 기존 논문 코드를 freeze
2. detector/verifier 핵심 로직만 추출
3. 새 인터페이스 wrapper 작성
4. replay dataset으로 old/new output 비교
5. 동일 입력에서 score 차이 확인
6. 차이가 허용 범위 내일 때만 새 파이프라인에 편입

---

## 3.8 실데이터가 도착하기 전 반드시 만들어야 할 것

## 3.8.1 Offline replay runner
폴더/manifest 기반 입력을 순서대로 재생하며 전체 파이프라인을 실행하는 도구가 필요하다.

필수 기능:
- multi-camera timestamp replay
- frame drop simulation
- artificial delay injection
- detector/verifier on-off ablation
- result dump

## 3.8.2 Event logger
각 단계에서 다음을 남겨야 한다.

- 입력 수신 시각
- detector latency
- verification request 생성 시각
- stage2 응답 도착 시각
- final state
- timeout 여부
- block/review/reject 사유

## 3.8.3 Mock actuator / policy simulator
실제 장치 없이도 다음을 테스트할 수 있어야 한다.

- decision event 전달 성공 여부
- decision latency
- retry / drop / timeout
- blocked 상태에서 인터페이스가 호출되지 않는지

## 3.8.4 Failure analysis tool
실패 유형을 자동 분류하는 도구가 필요하다.

예시 taxonomy:
- missed detection
- bad handoff
- verification failure
- tracking identity switch
- calibration mismatch
- timestamp drift
- poor image quality
- OOD sample
- policy over-blocking

---

## 3.9 실데이터 확보 후 바로 진행할 방향

## 3.9.1 1차 목표는 재학습이 아니라 data audit
실데이터가 오면 먼저 확인할 것은 성능이 아니라 분포와 품질이다.

우선 확인 항목:
- 해상도 / 비율 / 포맷
- 시간 동기화 상태
- 카메라별 노이즈 특성
- blur / saturation / glare
- object size distribution
- 낮/밤/거리/배경 변화
- annotation 가능 여부
- 누락 메타데이터 존재 여부

## 3.9.2 Canonical schema 고정
raw data는 그대로 보존하고, 별도의 canonical schema로 변환해야 한다.

권장 포함 항목:
- sample_id
- sequence_id
- camera_id
- timestamp
- image_ref
- calibration_ref
- environment tag
- label status
- split tag

## 3.9.3 Threshold 및 uncertainty 재조정
논문용 threshold는 실데이터에서 거의 그대로 안 맞을 가능성이 높다.  
따라서 실데이터 기반으로 다음을 다시 맞춰야 한다.

- stage1 detection threshold
- verification threshold
- trigger threshold
- manual review threshold
- timeout / persistence threshold

## 3.9.4 Specialized detector 통합 준비
다른 연구자의 전용 detector가 들어오면 바로 비교 가능해야 한다.

필요 사항:
- 동일 input adapter 사용
- 동일 output schema 사용
- detector registry에서 선택 가능
- 동일 replay set에서 A/B test 가능
- detector-verifier 조합별 report 자동 생성

---

## 4. 데이터 확보 후 추가로 해야 할 연구 및 실험

이 부분은 기존 두 논문 방향을 넘어서, **실환경 중심 thesis3**를 위해 특히 중요하다.

## 4.1 Trigger-to-verification handoff 안정성 연구
실제 시스템에서는 detector 자체보다도, 1차 카메라에서 2차 카메라로 후보가 제대로 넘어가는지가 중요하다.

연구 질문 예시:
- trigger 생성 시점의 오차가 verification 성공률에 얼마나 영향을 주는가?
- camera calibration 오차가 ROI handoff에 미치는 영향은?
- handoff timeout이 길수록 정확도는 올라가지만 latency는 얼마나 악화되는가?

지표 예시:
- handoff success rate
- re-acquisition rate
- handoff latency
- projected ROI IoU

## 4.2 Multi-zoom scheduling 정책 연구
모든 후보를 재확인할 수 없으므로 제한된 verification budget 안에서 어떤 후보를 우선 검증할지 연구해야 한다.

연구 질문 예시:
- confidence-based scheduling과 size-based scheduling 중 무엇이 유리한가?
- fixed top-k와 adaptive budget 중 어느 쪽이 실제 운영에 안정적인가?
- verifier를 언제 켜는 것이 총 false alarm을 가장 잘 줄이는가?

## 4.3 Small-object verifier의 domain shift 대응 연구
기존 verifier가 논문 데이터에서는 잘 되어도 실제 측정 데이터의 blur, 흔들림, 조명 변화에 약할 수 있다.

연구 항목:
- tiny object crop 품질 저하에 대한 강건성
- background clutter 증가 시 verifier score 분포 변화
- day/night, weather, device별 generalization
- re-calibration 또는 lightweight finetuning 필요성

## 4.4 Temporal verification 연구
단일 프레임 verifier만으로는 실제 환경에서 불안정할 수 있다.  
여러 프레임을 묶어 검증하는 temporal verifier 또는 track-level verifier가 필요할 수 있다.

연구 질문 예시:
- 1-frame verifier보다 3~5 frame aggregation이 더 안정적인가?
- verifier score smoothing이 오탐을 줄이는가?
- temporal context가 작은 객체 식별에 실질적으로 도움이 되는가?

## 4.5 Uncertainty calibration 및 reject option 연구
실환경에서는 잘못 확신하는 모델이 가장 위험하다.  
따라서 단순 confidence가 아니라 calibration과 reject 정책을 함께 연구해야 한다.

연구 항목:
- ECE/Brier score 기반 calibration
- confidence와 실제 precision의 일치도
- low-confidence / high-risk sample을 review queue로 보내는 정책
- detector와 verifier 점수를 결합한 uncertainty score 설계

## 4.6 OOD 및 입력 품질 추정 연구
실데이터는 논문 데이터와 다르게 out-of-distribution 샘플이 많다.

연구 항목:
- blur / glare / occlusion / saturation quality estimator
- OOD detector를 통한 low-trust sample 분리
- quality-aware verification gating
- poor-quality sample에서의 graceful degradation 정책

## 4.7 Tracking 및 identity consistency 연구
실환경에서는 같은 대상을 계속 같은 대상으로 유지하는 문제가 중요하다.

연구 항목:
- zoom 변화 시 identity switch 감소 방법
- multi-camera association
- short-term loss 후 re-identification
- tracker state가 verifier 성능에 미치는 영향

## 4.8 Active learning / annotation efficiency 연구
실제 측정 데이터는 annotation 비용이 크다.  
따라서 어떤 샘플을 먼저 라벨링할지 자체가 연구 주제가 된다.

연구 항목:
- verifier disagreement 기반 샘플 선택
- OOD/high-uncertainty sample 우선 라벨링
- failure case mining
- human review log를 weak label로 재사용하는 방법

## 4.9 Real-time budget / graceful degradation 연구
실제 시스템에서는 항상 full pipeline을 돌릴 수 없다.

연구 항목:
- detector FPS 저하 시 어떤 모듈부터 축소할 것인가?
- verifier budget을 줄였을 때 성능 손실은 얼마나 되는가?
- camera drop 또는 stage2 unavailable 상황에서 fallback은 무엇인가?

## 4.10 System-level evaluation 연구
논문에서는 보통 detector mAP나 verifier accuracy로 끝나지만, 실제 시스템에서는 그걸로 부족하다.

추가 지표 예시:
- end-to-end confirmation rate
- false alarm per hour
- missed event rate
- review queue rate
- average decision latency
- handoff failure rate
- calibration-drift sensitivity
- per-camera robustness gap

## 4.11 Simulator / hardware-in-the-loop 연구
실데이터가 들어와도 모든 실험을 실제 장비에서 바로 반복하기는 어렵다.  
그래서 replay simulator와 hardware-in-the-loop 환경이 중요하다.

연구 항목:
- recorded sequence replay 기반 반복 실험
- delay/fault injection
- calibration error injection
- synthetic perturbation 기반 stress test

---

## 5. thesis3 관점에서 기대 가능한 연구 축

기존 두 논문이 detector/verifier의 모델링 또는 token/작은 객체 인식 측면에 가까웠다면, thesis3는 다음과 같은 시스템 지향 기여로 재정의할 수 있다.

### 축 1. 실환경 다단계 인지 파이프라인
- detection-verification-tracking-handoff를 하나의 시스템으로 정리
- stage 간 정보 전달 구조와 실환경 안정성 분석

### 축 2. 실환경 작은 객체 검증
- small-object verifier를 실제 측정 환경에 맞게 재구성
- temporal / multi-view / quality-aware verification으로 확장

### 축 3. 불확실성과 안전 게이트
- 모델 score를 시스템 decision으로 바꾸는 과정 연구
- reject / review / block 정책을 포함한 운영형 설계

### 축 4. 데이터 중심 운영 루프
- 실데이터 유입 후 failure mining, active learning, threshold retuning을 포함한 지속 개선 구조

### 축 5. 시스템 지표 기반 평가 프레임워크
- 모델 단일 지표가 아니라 end-to-end KPI를 제시
- 실환경 robustness를 수치화

---

## 6. 권장 개발 단계

## 단계 0. 지금 당장
목표: 논문 코드와 시스템 코드 분리

할 일:
- 기존 논문 코드 freeze
- 공통 타입 정의
- detector/verifier wrapper 작성
- offline replay runner 생성
- event logger 생성

## 단계 1. 데이터 도착 직후
목표: 데이터 audit 및 canonical schema 고정

할 일:
- 포맷 확인
- 카메라별 메타데이터 정리
- quality audit
- annotation feasibility 점검
- baseline replay 실행

## 단계 2. 임시 검증 플랫폼 안정화
목표: 시나리오 A/B를 같은 프레임워크에서 모두 실행 가능하게 만들기

할 일:
- scenario A pipeline 구현
- scenario B pipeline 구현
- mock actuator 연결
- report 자동화
- detector/verifier 조합 실험

## 단계 3. 시스템 연구 시작
목표: thesis3에 들어갈 실환경 중심 연구 문제를 본격화

할 일:
- handoff 연구
- multi-zoom scheduling 연구
- uncertainty/reject 연구
- temporal verification 연구
- system KPI 설정

## 단계 4. 실제 구현 연계
목표: perception stack을 실제 장비 인터페이스로 이식 가능한 수준으로 정리

할 일:
- hardware adapter spec 정의
- API/IPC interface 고정
- timeout/fail-safe spec 고정
- shadow mode 테스트

---

## 7. 당장 필요한 산출물 체크리스트

### 필수 코드 산출물
- detector interface
- verifier interface
- tracker interface
- scenario A pipeline
- scenario B pipeline
- offline replay runner
- config loader
- logger / event store
- evaluation report script
- mock actuator simulator

### 필수 데이터 산출물
- canonical schema 문서
- camera metadata 문서
- calibration 관리 규칙
- replay manifest 포맷
- failure taxonomy 문서

### 필수 실험 산출물
- detector-only baseline
- detector + verifier baseline
- scenario A vs scenario B 비교
- threshold sweep 결과
- quality bucket별 성능 분석
- latency budget 분석

---

## 8. 결론

지금 시점의 핵심은 모델을 더 복잡하게 만드는 것이 아니라, **실데이터를 넣으면 끝까지 돌아가고, 어디서 실패했는지 알 수 있으며, detector/verifier를 바꿔 끼울 수 있는 시스템 베이스를 먼저 만드는 것**이다.

즉, 다음 순서가 맞다.

1. 논문 코드를 reference로 남긴다.
2. 시스템형 코드 베이스를 새로 만든다.
3. detector/verifier/tracker를 plugin으로 연결한다.
4. 실제 장치 전에는 mock/simulator로 검증한다.
5. 실데이터가 오면 먼저 data audit와 threshold/quality 분석을 한다.
6. 그 다음에야 thesis3용 실환경 연구 주제를 본격적으로 판다.

이 문서의 관점에서 보면, 지금 가장 중요한 것은 “모델 SOTA”가 아니라 **실환경 파이프라인의 안정성, 관측 가능성, 재현성, 확장성**이다.
