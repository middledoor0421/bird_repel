# central/ingest/reader.py
from typing import Optional, Tuple
import cv2
import time

class FrameReader:
    """Simple video reader wrapper for file/RTSP source."""
    def __init__(self, uri: str, width: int, height: int, fps: int) -> None:
        self.uri = uri
        self.cap = cv2.VideoCapture(uri)
        self.width = width
        self.height = height
        self.fps = fps
        if self.width > 0 and self.height > 0:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

    def read(self) -> Tuple[Optional[int], Optional[any]]:
        """Return (timestamp_ms, frame BGR) or (None, None) if end."""
        ok, frame = self.cap.read()
        if not ok:
            return None, None
        ts_ms = int(time.time() * 1000)
        return ts_ms, frame

    def release(self) -> None:
        if self.cap:
            self.cap.release()
