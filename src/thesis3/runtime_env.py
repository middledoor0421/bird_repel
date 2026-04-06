from __future__ import annotations

import os
import platform
import sys
from typing import Any


def collect_runtime_environment() -> dict[str, Any]:
    return {
        "python_executable": sys.executable,
        "python_version": sys.version.replace("\n", " "),
        "platform": platform.platform(),
        "cwd": os.getcwd(),
        "conda_default_env": os.environ.get("CONDA_DEFAULT_ENV"),
        "conda_prefix": os.environ.get("CONDA_PREFIX"),
    }
