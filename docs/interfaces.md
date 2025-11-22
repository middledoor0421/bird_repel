# BirdTarget Event (Central → Laser)

| Field        | Type      | Unit/Format        | Required | Description |
|--------------|-----------|--------------------|---------:|-------------|
| track_id     | string    | UUID or int-str    |    yes   | Central tracker ID (stable within session) |
| t            | int64     | epoch(ms)          |    yes   | Event timestamp (ms) |
| cam_id       | string    | e.g., "cam-N", "N" |    yes   | One of 4 central cameras |
| bearing      | float32   | degrees            |    yes   | Horizontal angle from image center (+right/-left) |
| box          | float32[] | [x, y, w, h] (px)  |    yes   | Bounding box in pixel coordinates |
| conf         | float32   | [0,1]              |    yes   | IoU‑aware confidence (VFL/GFLv2 aligned) |
| size_px      | int32     | pixels^2           |    yes   | Box area (px²) |
| need_recheck | bool      | -                  |    yes   | True if small/low‑conf → Laser applies conservative verify |
| meta         | dict      | optional fields    |     no   | Optional (e.g., detector_version) |

Notes
- conf는 VFL/GFLv2로 학습된 **품질 정렬 점수**입니다.
- bearing 변환(픽셀→각)은 common 유틸에서 제공됩니다.
