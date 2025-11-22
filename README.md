# bird_repel
Central camera (1st-stage) detects birds and publishes BirdTarget (bearing/box). Laser (2nd-stage) handles re‑verification, safety, and centering.
프로젝트 개요(중앙/레이저 역할 요약)

“현 단계 스코프: 중앙 카메라 시스템 v1 구현 중(레이저는 후속)”

KPI(중앙 AP_S/Recall/AP75, 지연 ≤ 100ms/스트림)

모듈 로드맵(ROI 게이팅 → 1차 탐지 → 추적 → 조건부 SAHI → BirdTarget 이벤트)
