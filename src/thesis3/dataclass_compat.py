from __future__ import annotations

from dataclasses import asdict, dataclass as _stdlib_dataclass, field, is_dataclass, replace
import sys
from typing import Any, Callable


def dataclass(*args: Any, **kwargs: Any) -> Callable[..., Any]:
    if sys.version_info < (3, 10):
        kwargs = dict(kwargs)
        kwargs.pop("slots", None)
    return _stdlib_dataclass(*args, **kwargs)


__all__ = ["asdict", "dataclass", "field", "is_dataclass", "replace"]
