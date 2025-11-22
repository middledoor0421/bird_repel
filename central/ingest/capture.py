# central/ingest/capture.py
# Python 3.9 compatible. Comments in English.
import threading
import time
from typing import Optional, Tuple
import cv2
import numpy as np
from loguru import logger

from .reader import FrameReader


class LatestFrameStore:
    """Thread-safe store that keeps only the latest frame."""
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame: Optional[np.ndarray] = None
        self._ts_ms: Optional[int] = None
        self._seq_w: int = 0  # written seq
        self._seq_r: int = 0  # last read seq

    def update(self, ts_ms: int, frame: np.ndarray) -> None:
        with self._lock:
            self._frame = frame
            self._ts_ms = ts_ms
            self._seq_w += 1

    def pop_latest(self) -> Tuple[Optional[int], Optional[np.ndarray], int]:
        """Return the latest frame once; also report dropped count since last pop.
        Returns: (ts_ms, frame_copy, dropped)
        If no new frame has been written since last pop, returns (None, None, 0).
        """
        with self._lock:
            if self._seq_w == self._seq_r:
                return None, None, 0
            dropped = max(0, self._seq_w - self._seq_r - 1)
            self._seq_r = self._seq_w
            ts_ms = self._ts_ms if self._ts_ms is not None else int(time.time() * 1000)
            # Copy to avoid race with writer replacing the buffer
            out = None
            if self._frame is not None:
                out = self._frame.copy()
            return ts_ms, out, dropped


class CaptureWorker(threading.Thread):
    """Per-camera capture worker that continuously updates LatestFrameStore."""
    def __init__(self, cam_id: str, uri: str, width: int, height: int, fps: int,
                 store: LatestFrameStore, reconnect_backoff_s: float = 2.0) -> None:
        super().__init__(daemon=True)
        self.cam_id = cam_id
        self.uri = uri
        self.width = width
        self.height = height
        self.fps = fps
        self.store = store
        self._stop = threading.Event()
        self._backoff = reconnect_backoff_s
        self._reader: Optional[FrameReader] = None

    def _open_reader(self) -> None:
        self._reader = FrameReader(uri=self.uri, width=self.width, height=self.height, fps=self.fps)

    def run(self) -> None:
        logger.info("[{}] CaptureWorker started ({}x{} @{}fps)", self.cam_id, self.width, self.height, self.fps)
        self._open_reader()
        while not self._stop.is_set():
            try:
                if self._reader is None:
                    self._open_reader()
                ts_ms, frame = self._reader.read() if self._reader is not None else (None, None)
                if frame is None:
                    # End of stream or read error; try to reconnect
                    logger.warning("[{}] frame read failed; reconnecting in {:.1f}s", self.cam_id, self._backoff)
                    time.sleep(self._backoff)
                    if self._reader is not None:
                        self._reader.release()
                    self._open_reader()
                    continue
                # Update latest frame store
                if ts_ms is None:
                    ts_ms = int(time.time() * 1000)
                self.store.update(ts_ms, frame)
            except Exception as e:
                logger.exception("[{}] Capture error: {}", self.cam_id, e)
                time.sleep(self._backoff)
                try:
                    if self._reader is not None:
                        self._reader.release()
                except Exception:
                    pass
                self._reader = None

        # cleanup
        try:
            if self._reader is not None:
                self._reader.release()
        except Exception:
            pass
        logger.info("[{}] CaptureWorker stopped", self.cam_id)

    def stop(self) -> None:
        self._stop.set()
