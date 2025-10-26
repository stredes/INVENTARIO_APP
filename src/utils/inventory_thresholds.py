from __future__ import annotations

"""
Persistencia simple (JSON) de límites críticos por producto.

Se guarda en app_data/inventory_thresholds.json un diccionario:
  { "<product_id>": {"min": int, "max": int}, ... }

Uso:
  get_thresholds(pid, default_min, default_max) -> (min,max)
  set_thresholds(pid, min_v, max_v)
"""

from pathlib import Path
import json
from typing import Tuple


_FILE = Path("app_data/inventory_thresholds.json")


def _load() -> dict:
    try:
        if _FILE.exists():
            return json.loads(_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save(data: dict) -> None:
    try:
        _FILE.parent.mkdir(parents=True, exist_ok=True)
        _FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def get_thresholds(product_id: int, default_min: int, default_max: int) -> Tuple[int, int]:
    data = _load()
    entry = data.get(str(product_id)) or {}
    try:
        mn = int(entry.get("min", default_min))
    except Exception:
        mn = int(default_min)
    try:
        mx = int(entry.get("max", default_max))
    except Exception:
        mx = int(default_max)
    return mn, mx


def set_thresholds(product_id: int, min_value: int, max_value: int) -> None:
    data = _load()
    data[str(product_id)] = {"min": int(min_value), "max": int(max_value)}
    _save(data)


def clear_threshold(product_id: int) -> None:
    data = _load()
    if str(product_id) in data:
        data.pop(str(product_id), None)
        _save(data)


__all__ = ["get_thresholds", "set_thresholds", "clear_threshold"]

