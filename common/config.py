# common/config.py
from typing import Any, Dict
import yaml
from pathlib import Path

def load_yaml(path: str) -> Dict[str, Any]:
    """Load YAML config file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)
