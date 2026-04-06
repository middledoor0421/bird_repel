# total_log

이 폴더는 `project`의 진행 상황을 계속 관리하기 위한 작업 로그 폴더다.
목표는 "지금 어디까지 되었는지", "다음에 무엇을 해야 하는지", "왜 그렇게 결정했는지"를 빠르게 복원할 수 있게 하는 것이다.

## 파일 구성

- `current_status.md`
  - 현재 시스템이 어디까지 구현되었는지 요약
- `backlog.md`
  - 앞으로 해야 할 작업과 우선순위
- `work_log.md`
  - 날짜별 작업 기록
- `external_model_onboarding.md`
  - 외부 detector / verifier / safety 모듈 연결 후보와 사용 경로 정리
- `templates/work_log_entry_template.md`
  - 새 작업 로그를 추가할 때 복사해서 쓸 템플릿

## 운영 규칙

1. 큰 기능을 추가하거나 구조를 바꾸면 `work_log.md`에 먼저 남긴다.
2. 현재 시스템 상태가 달라졌으면 `current_status.md`를 함께 갱신한다.
3. 다음 우선순위가 바뀌면 `backlog.md`를 갱신한다.
4. 실험 결과나 임시 메모는 가능하면 `memo/` 또는 별도 결과 폴더에 두고, 여기에는 "작업 관리 관점"만 기록한다.

## 현재 기준

- 기준 날짜: `2026-04-03`
- 현재 중점: detector-only baseline을 유지하면서, 실데이터 적응용 방법론을 계속 교체할 수 있는 구조 정리
- 현재 축:
  - offline replay 기반 파이프라인
  - MP4 기반 GT/annotation 준비 흐름
  - live/pseudo-live CCTV 입력 어댑터
  - latency / burden logging
  - detector / trigger policy / candidate selector 교체 실험 구조
  - environment profile / verification scheduler / confirmation policy 훅
