# 논문 중심 연구와 실제 시스템 연구의 차이: 시스템 연구 관점 정리

## 문서 목적
이 문서는 논문을 쓰기 위해 진행하던 연구와, 실제 구현을 목표로 진행해야 하는 연구가 **무엇이 다르고 왜 다른지**를 개념적으로 정리한 것이다.  
특히 AI 모델 자체의 성능 향상보다, **시스템 연구의 관점에서 무엇을 봐야 하는지**에 초점을 둔다.

---

## 1. 한 문장으로 정리하면

논문 중심 연구는 보통 **"어떤 아이디어가 benchmark에서 성능 향상을 주는가"**를 묻는다.  
반면 시스템 연구는 **"현실의 불완전한 입력, 지연, 오류, 장치 제약 속에서도 전체 파이프라인이 목적에 맞게 안정적으로 동작하는가"**를 묻는다.

이 둘은 연결되어 있지만, 질문의 단위와 성공의 기준이 다르다.

---

## 2. 왜 이 차이를 분리해서 봐야 하는가

논문용 연구에서는 다음이 가능하다.

- 잘 정리된 dataset
- 고정된 train/val/test split
- 단일 지표 중심 비교
- 평균 성능 중심 해석
- 실패 사례가 있어도 논문 메시지가 유지되면 괜찮음

하지만 실제 시스템에서는 다음이 발생한다.

- 입력이 매번 달라짐
- 센서가 끊기거나 timestamp가 어긋남
- 카메라별 품질 차이가 큼
- latency budget이 있음
- 어떤 실패는 드물어도 치명적임
- 사람이 보고 판단하는 운영 흐름까지 포함됨

즉, 논문 관점에서는 “좋은 모델”이 중요하지만, 시스템 관점에서는 “믿고 운영 가능한 구조”가 더 중요해진다.

---

## 3. 논문 연구와 시스템 연구의 핵심 차이

## 3.1 질문의 단위가 다르다

### 논문 연구의 질문
- 이 모듈이 기존보다 정확한가?
- 이 verifier가 작은 객체에서 더 좋은가?
- 이 detector가 token reduction이나 feature design 덕분에 더 유리한가?

### 시스템 연구의 질문
- detector, verifier, tracker, trigger가 합쳐졌을 때 전체 성능은 어떠한가?
- 한 단계의 개선이 전체 시스템 목적에 실제로 의미 있는가?
- 어느 단계가 전체 오류의 병목인가?
- 어떤 실패는 모델보다 인터페이스나 동기화 문제에서 생기지 않는가?

즉, 논문 연구는 **component question**, 시스템 연구는 **end-to-end question**에 가깝다.

---

## 3.2 성공 기준이 다르다

### 논문 연구의 성공 기준
- SOTA 또는 baseline 대비 개선
- benchmark metric 향상
- ablation으로 아이디어의 유효성 입증

### 시스템 연구의 성공 기준
- 운영 가능한 latency 내에서 동작
- 분포 변화에도 성능이 급락하지 않음
- 실패 시 안전하게 멈추거나 review로 넘김
- 장시간 반복 실험에서 상태가 무너지지 않음
- 로그와 진단 정보로 원인을 추적 가능

논문에서는 평균 정확도 1% 개선이 중요할 수 있지만, 시스템에서는 **치명적 오작동 1건 감소**가 더 중요할 수 있다.

---

## 3.3 데이터에 대한 가정이 다르다

### 논문 연구
- 데이터가 이미 정리되어 있음
- label이 존재함
- train/test 분포가 어느 정도 통제됨
- 누락/오염 샘플은 적거나 사전 정리됨

### 시스템 연구
- 데이터 수집 과정 자체가 연구 대상이 됨
- label이 늦게 붙거나 일부만 존재함
- 분포가 시간에 따라 바뀜
- 장비마다 데이터 특성이 다름
- calibration drift, blur, glare, occlusion 같은 현실 요소가 들어옴

따라서 시스템 연구에서는 모델 구조만큼이나 **data audit, schema, logging, failure mining**이 중요하다.

---

## 3.4 실패를 다루는 방식이 다르다

### 논문 연구
실패는 주로 “한계” 또는 “future work”로 정리된다.

### 시스템 연구
실패는 반드시 분류되고, 재현되고, 완화되어야 한다.

예를 들어 시스템 연구는 다음을 본다.

- detector miss인지
- verifier fail인지
- tracker identity switch인지
- handoff mismatch인지
- timestamp drift인지
- quality issue인지
- OOD sample인지
- threshold/policy 문제인지

즉, 시스템 연구는 “실패를 설명하는 것”을 넘어서 **실패를 운영 가능한 단위로 관리하는 것**이 핵심이다.

---

## 3.5 인터페이스의 중요성이 다르다

논문에서는 detector와 verifier가 한 코드 안에서 얽혀 있어도 큰 문제가 아닐 수 있다.  
하지만 시스템에서는 인터페이스가 설계의 중심이 된다.

왜냐하면 실제 시스템은 다음과 같기 때문이다.

- detector가 바뀔 수 있음
- verifier가 추가될 수 있음
- 카메라가 늘어날 수 있음
- 실제 장치 인터페이스가 나중에 붙을 수 있음
- 사람이 중간에 review할 수 있음

따라서 시스템 연구에서는 성능 그 자체 못지않게 다음이 중요하다.

- 입력/출력 schema
- stage 간 contract
- timeout 규칙
- 에러 처리 정책
- 상태 전이(state transition)

이 지점이 논문용 코드와 시스템용 코드가 가장 크게 갈리는 부분이다.

---

## 3.6 시간 개념이 다르다

논문 연구는 주로 frame-wise, sample-wise로 생각한다.  
하지만 시스템 연구는 시간 흐름 위에서 생각해야 한다.

예를 들어 시스템에서는 다음이 중요하다.

- frame arrival delay
- detector latency
- verification deadline
- track persistence
- timeout 후 fallback
- long-run memory leak
- 장시간 동작 시 state accumulation

즉, 시스템 연구는 정적인 샘플 정확도가 아니라 **시간 위에서 깨지지 않는가**를 본다.

---

## 3.7 지표 체계가 다르다

### 논문 연구 지표
- accuracy
- precision/recall
- mAP
- F1
- AUROC

### 시스템 연구 지표
- end-to-end confirmation rate
- false alarm per hour
- missed event rate
- handoff success rate
- average / tail latency
- review rate
- blocked rate
- recovery time after fault
- long-run stability
- per-device robustness gap

즉, 시스템 연구에서는 모델 지표가 필요하지만 충분하지 않다.  
반드시 **운영 지표**가 추가되어야 한다.

---

## 4. 시스템 연구의 핵심 사고방식

## 4.1 모듈 최적화가 아니라 목적 최적화
논문에서는 detector accuracy가 높아지면 좋은 결과처럼 보인다.  
하지만 시스템에서는 detector accuracy가 높아도 전체 목적에 별 도움이 없을 수 있다.

예를 들어:
- detector가 좋아졌지만 verification handoff가 실패하면 전체 시스템은 개선되지 않음
- verifier가 좋아졌지만 latency가 너무 커서 deadline을 놓치면 운영 성능은 오히려 나빠짐
- confidence가 높아져도 calibration이 나쁘면 잘못된 확신만 늘어날 수 있음

따라서 시스템 연구에서는 항상 이렇게 물어야 한다.

- 이 개선이 end-to-end 목적 함수에 실제로 기여하는가?
- 이 모듈이 전체 병목인가?
- 다른 단계와 결합했을 때도 이득이 유지되는가?

---

## 4.2 평균 성능보다 꼬리 위험을 본다
시스템은 평균이 좋아도, 특정 드문 조건에서 크게 무너지면 운영상 문제가 된다.  
그래서 시스템 연구는 tail case를 중요하게 본다.

예시:
- 작은 객체 + 저조도 + blur 조합
- 카메라 간 timestamp mismatch
- stage2 카메라 지연
- 특정 배경에서 반복되는 false positive
- calibration drift가 누적된 조건

논문은 평균 성능을 말하지만, 시스템 연구는 **어떤 조건에서 언제, 왜 무너지는가**를 따진다.

---

## 4.3 정확도보다 관측 가능성(observability)을 중시한다
논문 코드는 결과만 나오면 되는 경우가 많다.  
하지만 시스템 코드는 결과보다도 **왜 그 결과가 나왔는지 추적 가능해야 한다.**

그래서 시스템 연구에서는 다음이 필수다.

- stage별 intermediate output 저장
- timestamp logging
- model version / config hash 저장
- error code 체계화
- failure case replay 가능 구조

관측 가능성이 없으면, 실데이터에서 문제가 생겨도 개선이 아니라 추측만 하게 된다.

---

## 4.4 “잘 동작함”보다 “잘 실패함”을 설계한다
좋은 시스템은 항상 맞는 시스템이 아니라, **틀릴 때도 관리 가능한 시스템**이다.

시스템 연구에서 중요한 질문:
- 확신이 낮을 때 어떻게 할 것인가?
- 입력 품질이 나쁠 때 차단할 것인가, review로 보낼 것인가?
- stage2가 없으면 fallback은 무엇인가?
- OOD가 감지되면 어떤 상태로 전이할 것인가?

즉, 시스템 연구는 fail-safe와 degrade policy를 함께 설계한다.

---

## 5. 시스템 연구자는 무엇을 먼저 정의해야 하는가

## 5.1 시스템 경계
무엇을 시스템 안으로 보고, 무엇을 밖으로 둘지 먼저 정해야 한다.

예시:
- 입력: camera frames / metadata / calibration / clock
- 내부: detection / verification / tracking / decision state
- 외부: operator review / hardware adapter / storage backend

경계를 정하지 않으면 논의가 끝없이 퍼진다.

---

## 5.2 상태(state)와 전이(transition)
시스템 연구는 함수 호출보다 상태 전이로 보는 것이 좋다.

예시 상태:
- `NEW_CANDIDATE`
- `TRACKING`
- `VERIFICATION_REQUESTED`
- `VERIFIED`
- `REVIEW_REQUIRED`
- `REJECTED`
- `TIMEOUT`
- `BLOCKED`

이렇게 보면 다음이 쉬워진다.
- timeout 정의
- retry 정책
- failure localization
- operator intervention 지점 정의

---

## 5.3 계약(contract)
시스템은 사람 간 협업과 모듈 교체가 전제되므로, contract가 중요하다.

예시 contract:
- detector output schema
- verifier request format
- track update rules
- review queue payload
- log record schema

좋은 system research는 종종 “새로운 모델”만이 아니라 **좋은 contract와 evaluation protocol**을 만든다.

---

## 5.4 실험의 단위
시스템 연구에서는 실험도 계층적으로 해야 한다.

### Level 1. Component experiment
- detector만 평가
- verifier만 평가
- tracker만 평가

### Level 2. Interface experiment
- detector output이 verifier에 잘 전달되는가?
- handoff가 얼마나 정확한가?
- multi-camera sync가 유지되는가?

### Level 3. Pipeline experiment
- end-to-end confirmation rate는 어떠한가?
- latency budget을 만족하는가?
- 특정 단계 제거 시 전체 성능은 어떻게 바뀌는가?

### Level 4. Operational experiment
- 장시간 replay에서 메모리/상태가 안정적인가?
- fault injection 시 graceful degradation이 되는가?
- review queue가 과도하게 쌓이지 않는가?

이 레벨 구조가 없으면, 실험은 많은데 시스템 이해는 얕아진다.

---

## 6. 논문 중심 사고에서 시스템 연구 사고로 바꾸려면

## 6.1 “모델을 바꾸면 좋아질까?” 대신 “어디가 병목인가?”를 묻는다
실제 시스템에서는 detector보다 handoff가 더 큰 병목일 수도 있다.  
또는 verifier보다 quality filtering이 더 중요할 수도 있다.

따라서 먼저 해야 할 일은 모델 교체가 아니라:
- 병목 파악
- failure taxonomy 정리
- 운영 지표 설정
- stage별 ablation

---

## 6.2 “더 좋은 score” 대신 “더 좋은 운영 상태”를 묻는다
예를 들면 다음이 더 시스템 연구다운 질문이다.

- false alarm per hour를 줄였는가?
- review queue burden을 줄였는가?
- 동일한 latency 예산 안에서 더 안정적인가?
- hard case에서 과신을 줄였는가?

이 질문들은 단순 accuracy 개선보다 실제 구현과 더 가깝다.

---

## 6.3 “한 번의 실험” 대신 “지속 가능한 루프”를 만든다
시스템 연구는 실험 한 번으로 끝나지 않는다.  
다음 루프를 설계해야 한다.

1. 데이터 수집
2. replay
3. 실패 분석
4. 라벨링 우선순위 결정
5. threshold/model 수정
6. 재평가
7. 운영 로그 축적
8. 다시 failure mining

즉, 시스템 연구는 **continuous improvement loop**를 설계하는 일이다.

---

## 7. 실제 구현에 필요한 연구는 어떻게 바라봐야 하는가

실제 구현에 필요한 연구는 단순히 “실제 데이터를 더 모아 성능을 높이는 일”이 아니다.  
오히려 다음 네 갈래를 동시에 본다.

## 7.1 인지(perception) 연구
- detector
- verifier
- tracker
- uncertainty
- OOD detection

## 7.2 구조(architecture) 연구
- multi-stage pipeline
- trigger/handoff
- scheduling
- state machine
- interface 설계

## 7.3 운영(operations) 연구
- logging
- monitoring
- replay
- failure taxonomy
- threshold retuning process

## 7.4 인간-시스템 상호작용 연구
- review queue 설계
- operator burden
- alert quality
- decision explanation

논문은 보통 7.1에 몰리지만, 실제 시스템 연구는 7.2~7.4까지 같이 봐야 한다.

---

## 8. 시스템 연구 관점에서 thesis3를 구성한다면

thesis3를 시스템 중심으로 가져가려면, 단순히 “새 verifier를 제안했다”로는 약할 수 있다.  
오히려 다음과 같이 구조화하는 것이 더 자연스럽다.

### 8.1 핵심 문제 정의
- 실환경 다중 카메라 조건에서 작은 객체를 안정적으로 탐지/검증/추적하는 것은 왜 어려운가?
- 단일 detector metric으로는 왜 실제 성능을 설명할 수 없는가?

### 8.2 시스템 가설
- multi-stage verification이 false alarm을 줄인다
- temporal / multi-view 정보가 작은 객체의 검증 안정성을 높인다
- uncertainty-aware gating이 운영 안정성을 높인다
- detector 성능 향상만으로는 해결되지 않는 병목이 존재한다

### 8.3 기여 형태
- 시스템 아키텍처 제안
- stage 간 contract 설계
- 실환경 평가 프로토콜 제안
- failure taxonomy와 운영 지표 제안
- verifier/uncertainty/temporal aggregation 등 AI 모듈 기여

### 8.4 평가 방식
- component-level metric
- handoff / tracking metric
- end-to-end system KPI
- robustness / stress test
- latency / failure mode 분석

이런 구조라면 thesis3는 단순 모델 논문이 아니라 **실환경 지향 시스템 연구**로 자리 잡을 수 있다.

---

## 9. 시스템 연구자는 무엇을 기록해야 하는가

실제 시스템 연구를 하려면 결과보다 로그가 더 중요해지는 시점이 온다.  
반드시 남겨야 할 항목은 다음과 같다.

- input source
- timestamp
- camera id
- model version
- config version
- detector output
- verifier output
- track state
- policy state
- latency breakdown
- error code
- operator action(optional)

이 기록이 있어야 다음이 가능하다.
- 동일 실패 재현
- detector/verifier 교체 전후 비교
- threshold 변경 효과 분석
- 논문에 들어갈 실환경 failure analysis

---

## 10. 시스템 연구 체크리스트

아래 질문에 “예”가 많아질수록 시스템 연구에 가까워진다.

- component metric 말고 end-to-end KPI가 정의되어 있는가?
- 데이터 분포 변화에 대한 가정이 명시되어 있는가?
- 실패 유형이 taxonomy로 정리되어 있는가?
- detector/verifier/tracker가 교체 가능한 인터페이스로 분리되어 있는가?
- 운영 중 low-confidence case를 처리하는 정책이 있는가?
- replay와 fault injection이 가능한가?
- 장시간 실행에서 상태가 안정적인가?
- 로그만으로 원인 추적이 가능한가?
- 사람이 개입하는 흐름이 설계되어 있는가?
- 한 번의 모델 개선이 시스템 목적에 실제로 기여하는지 측정하는가?

---

## 11. 결론

논문 중심 연구와 실제 시스템 연구의 가장 큰 차이는, 전자가 **좋은 아이디어의 유효성**을 보이는 데 초점을 둔다면, 후자는 **현실에서 무너지지 않는 구조**를 만드는 데 초점을 둔다는 점이다.

시스템 연구의 관점에서는 다음이 핵심이다.

- 모델 하나보다 전체 흐름을 본다.
- 평균 성능보다 실패 양상을 본다.
- 정확도보다 운영 가능성과 관측 가능성을 본다.
- 더 똑똑한 모델보다 더 잘 정의된 인터페이스와 상태 전이를 중시한다.
- 실험 한 번보다 지속 가능한 개선 루프를 설계한다.

따라서 앞으로 실제 구현을 준비하는 단계에서는, 논문용 실험 습관을 그대로 연장하기보다 다음으로 시야를 전환해야 한다.

1. component improvement
2. interface and pipeline design
3. observability and failure management
4. real-data adaptation loop
5. end-to-end system evaluation

이 전환이 이루어질 때, 연구는 단순한 성능 개선을 넘어서 **실제 환경을 견디는 시스템 연구**가 된다.
