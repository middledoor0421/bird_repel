from __future__ import annotations

import importlib
import importlib.util
import inspect
from pathlib import Path
import sys
from typing import Any

from thesis3.core import stable_hash


def instantiate_dynamic_plugin(target: str, params: dict[str, Any]) -> Any:
    symbol = load_symbol(target)
    if inspect.isclass(symbol):
        return symbol(**params)
    if callable(symbol):
        return symbol(**params)
    raise TypeError(f"Dynamic plugin target is not callable: {target}")


def load_symbol(target: str) -> Any:
    if ":" not in target:
        raise ValueError(f"Dynamic plugin target must use '<module_or_path>:<symbol>' format: {target}")

    module_ref, symbol_name = target.rsplit(":", 1)
    if not symbol_name:
        raise ValueError(f"Dynamic plugin target is missing a symbol name: {target}")

    if _looks_like_file_target(module_ref):
        module = _load_module_from_file(module_ref)
    else:
        module = importlib.import_module(module_ref)

    try:
        return getattr(module, symbol_name)
    except AttributeError as exc:
        raise AttributeError(f"Symbol '{symbol_name}' not found in plugin target: {target}") from exc


def _looks_like_file_target(module_ref: str) -> bool:
    return module_ref.endswith(".py") or module_ref.startswith("/") or module_ref.startswith("./") or module_ref.startswith("../")


def _load_module_from_file(module_ref: str):
    module_path = Path(module_ref)
    if not module_path.is_absolute():
        module_path = (Path.cwd() / module_path).resolve()
    if not module_path.exists():
        raise FileNotFoundError(f"Dynamic plugin file does not exist: {module_path}")

    module_name = f"thesis3_plugin_{stable_hash(str(module_path))}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to create module spec for plugin file: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
