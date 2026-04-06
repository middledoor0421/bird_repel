# project

## English

This repository is a flexible experimentation platform for validating and adapting a real-world bird detection, verification, and safety system before deployment with actual field data.

The current goal is to keep a strong detector-only baseline while making intermediate methodology components easy to replace, compare, and refine as real data arrives.

### What is included

- Modular detector / verifier / tracker / policy pipeline
- Offline replay and pseudo-live execution paths
- MP4 -> annotation -> GT -> replay manifest preparation workflow
- Event / frame / verification / tracking GT evaluation tools
- Experiment suite comparison and markdown report generation
- Canonical schema, camera inventory, data audit, and stress replay tooling
- Ongoing logs and design notes for system evolution

### Key principles

- Keep a detector-only baseline as a fixed reference
- Treat prior methods such as `bird_sahi_temporal` and `ccs-lcs` as replaceable methodology candidates, not permanent architecture
- Optimize for fast iteration once real data arrives:
  - schema confirmation
  - initial data audit
  - GT generation
  - baseline vs. method comparison

### Main directories

- `src/thesis3`: core system code
- `apps`: CLI entry points
- `configs`: example and template configs
- `examples`: example inputs and fixtures
- `memo`: design notes
- `total_log`: current status, backlog, and work log

### Recommended entry points

- Current status: `total_log/current_status.md`
- Backlog: `total_log/backlog.md`
- Work log: `total_log/work_log.md`
- System design memo: `memo/system_base_and_research_plan_safe.md`

### Notes

- `artifacts/` contains generated outputs and is intentionally excluded from git
- The internal package path remains `src/thesis3` for code compatibility

---

## 한국어

이 저장소는 실제 현장 데이터가 들어오기 전에, bird detection / verification / safety system을 검증하고 조정하기 위한 유연한 실험 플랫폼이다.

현재 목표는 detector-only baseline을 기준선으로 유지하면서, 중간 방법론을 쉽게 교체하고 비교하고 조정할 수 있게 준비해두는 것이다.

### 포함 내용

- modular detector / verifier / tracker / policy pipeline
- offline replay 및 pseudo-live 실행 경로
- MP4 -> annotation -> GT -> replay manifest 준비 흐름
- event / frame / verification / tracking GT 평가 도구
- 실험 suite 비교 및 markdown report 생성
- canonical schema, camera inventory, data audit, stress replay 도구
- 시스템 진행 상태와 설계 방향을 남기는 로그 및 메모

### 핵심 원칙

- detector-only baseline을 항상 기준선으로 유지한다
- `bird_sahi_temporal`, `ccs-lcs` 같은 기존 연구는 고정 구조가 아니라 교체 가능한 방법론 후보로 다룬다
- 실제 데이터가 오면 빠르게 다음 순서로 이어간다
  - schema 확정
  - 초기 data audit
  - GT 작성
  - baseline과 방법론 비교

### 주요 디렉터리

- `src/thesis3`: 핵심 시스템 코드
- `apps`: CLI 진입점
- `configs`: example / template config
- `examples`: 예제 입력과 fixture
- `memo`: 설계 메모
- `total_log`: 현재 상태, backlog, 작업 로그

### 시작 지점

- 현재 상태: `total_log/current_status.md`
- 다음 작업 목록: `total_log/backlog.md`
- 작업 기록: `total_log/work_log.md`
- 시스템 설계 메모: `memo/system_base_and_research_plan_safe.md`

### 비고

- `artifacts/`는 실행 결과와 생성물을 담는 디렉터리이며 git에는 포함하지 않는다
- 코드 호환성을 위해 내부 패키지 경로는 `src/thesis3`를 유지한다
