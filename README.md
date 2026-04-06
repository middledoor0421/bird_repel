# project

실데이터 기반 bird detection / verification / safety system을 실제 운영 환경에 맞게 검증하고 조정하기 위한 실험 플랫폼이다.

현재 저장소는 "실데이터가 왔을 때 바로 태워볼 수 있는 베이스"를 목표로 준비되어 있다. 핵심 방향은 다음과 같다.

- detector-only baseline을 항상 유지한다.
- `bird_sahi_temporal`, `ccs-lcs` 같은 기존 연구는 고정 구조가 아니라 교체 가능한 방법론 후보로 다룬다.
- 실제 데이터가 오면 `schema 확정 -> data audit -> GT 작성 -> baseline 및 방법론 비교` 순서로 이어간다.

## 포함 내용

- modular detector / verifier / tracker / policy pipeline
- offline replay 및 pseudo-live 실행 경로
- MP4 -> annotation -> GT -> replay manifest 준비 흐름
- event / frame / verification / tracking GT 평가 도구
- suite 비교 및 markdown report 생성
- canonical schema, camera inventory, data audit, stress replay 도구
- 진행 로그 및 운영 메모

## 주요 디렉터리

- `src/thesis3`: 핵심 시스템 코드
- `apps`: 실행용 CLI 진입점
- `configs`: example / template config
- `examples`: 예제 입력 및 fixture
- `memo`: 설계 메모
- `total_log`: 현재 상태, backlog, 작업 로그

## 시작 지점

- 현재 상태: `total_log/current_status.md`
- 다음 작업 목록: `total_log/backlog.md`
- 작업 기록: `total_log/work_log.md`
- 시스템 설계 메모: `memo/system_base_and_research_plan_safe.md`

## 비고

- `artifacts/`는 실행 결과와 생성물을 담는 디렉터리이며 git에는 포함하지 않는다.
- 실제 GitHub push를 하려면 이 로컬 저장소를 초기화한 뒤 remote를 연결해야 한다.
