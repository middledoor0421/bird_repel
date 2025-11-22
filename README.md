# Bird Repel — Central Camera System (CCS)

본 프로젝트는 중앙 카메라(4방)에서 원거리·소형 **새**를 실시간 탐지하여 **좌표/방위만** 레이저 시스템에 전달합니다.  
레이저(4줌)는 재확인·중앙정렬·안전 판정을 전담하며, 중앙은 발사/금지 로직에 **관여하지 않습니다**.  
(역할 분리의 상세 배경과 KPI는 내부 기획 문서를 따릅니다.) 

## Pipeline (CCS)
`Ingest → ROI Gating(Stage0) → Bird Detector(Stage1, Soft‑NMS/IoU‑aware) → Tracker → (Conditional SAHI) → BirdTarget Event`

- **목표 지표(예시)**: AP_S(소형), AP75(정밀) 상승 & 지연 ≤ 100ms/스트림
- **출력 이벤트**: `BirdTarget` (track_id, t, cam_id, bearing, box, conf, size_px, need_recheck)

## Repo layout (phase 1)

## Status
- Phase 1: 스캐폴드/설정/인터페이스 고정 중
- 다음 단계: Stage0/Stage1 스켈레톤 코드 추가, 리플레이/지표 로깅

(참조: 본 시스템은 중앙=1차 탐지/좌표 전달, 레이저=2차 재확인·정렬·안전을 전제로 설계되었습니다.)