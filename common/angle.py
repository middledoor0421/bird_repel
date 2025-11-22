# common/angle.py
from typing import Tuple

def pixels_to_bearing(xy: Tuple[float, float],
                      image_size: Tuple[int, int],
                      center_xy: Tuple[float, float],
                      fov_deg: float) -> float:
    """Convert pixel coordinate to horizontal bearing (degrees).

    Args:
        xy: (x, y) pixel.
        image_size: (width, height).
        center_xy: optical center (cx, cy) in pixels.
        fov_deg: horizontal field-of-view in degrees.

    Returns:
        Bearing in degrees (+right / -left).
    """
    x, _ = xy
    w, _ = image_size
    cx, _ = center_xy
    norm = (x - cx) / (w * 0.5)  # [-1, 1]
    return norm * (fov_deg * 0.5)
