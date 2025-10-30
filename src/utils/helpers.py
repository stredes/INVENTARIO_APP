from __future__ import annotations
import configparser
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import os
import sys

CONFIG_PATH = Path("config/settings.ini")
UI_STATE_PATH = Path("config/ui_state.ini")


def _frozen_dir() -> Path | None:
    try:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).parent
    except Exception:
        pass
    return None


def _meipass_dir() -> Path | None:
    try:
        base = getattr(sys, "_MEIPASS", None)
        if base:
            return Path(base)
    except Exception:
        pass
    return None


def _external_config_path() -> Path:
    exedir = _frozen_dir()
    if exedir is not None:
        return exedir / CONFIG_PATH
    return CONFIG_PATH

def _external_ui_state_path() -> Path:
    exedir = _frozen_dir()
    if exedir is not None:
        return exedir / UI_STATE_PATH
    return UI_STATE_PATH


# -----------------------------
# CONFIG
# -----------------------------
def _ensure_config_dir() -> None:
    _external_config_path().parent.mkdir(parents=True, exist_ok=True)


def read_config() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    p = _external_config_path()
    if p.exists():
        cfg.read(p, encoding="utf-8")
    else:
        mdir = _meipass_dir()
        if mdir is not None and (mdir / CONFIG_PATH).exists():
            cfg.read(mdir / CONFIG_PATH, encoding="utf-8")
    return cfg


def write_config(cfg: configparser.ConfigParser) -> None:
    _ensure_config_dir()
    p = _external_config_path()
    with open(p, "w", encoding="utf-8") as f:
        cfg.write(f)

# -----------------------------
# SECUENCIA PARA OC (persistida en ui_state.ini)
# -----------------------------
def get_next_po_sequence() -> int:
    """Lee la secuencia actual (siguiente) para OC desde ui_state.ini."""
    cfg = configparser.ConfigParser()
    p = _external_ui_state_path()
    if p.exists():
        cfg.read(p, encoding="utf-8")
    if "seq" not in cfg:
        cfg["seq"] = {}
    try:
        return int(cfg["seq"].get("po_next", "0"))
    except Exception:
        return 0


def bump_po_sequence() -> int:
    """Incrementa la secuencia y la guarda; retorna el valor usado."""
    cfg = configparser.ConfigParser()
    p = _external_ui_state_path()
    if p.exists():
        cfg.read(p, encoding="utf-8")
    if "seq" not in cfg:
        cfg["seq"] = {}
    try:
        current = int(cfg["seq"].get("po_next", "0"))
    except Exception:
        current = 0
    cfg["seq"]["po_next"] = str(current + 1)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        cfg.write(f)
    return current


def make_po_number(prefix: str = "OC-", width: int = 6) -> str:
    """Genera un número de OC secuencial: OC-000000, OC-000001, ..."""
    n = bump_po_sequence()
    try:
        return f"{prefix}{n:0{width}d}"
    except Exception:
        return f"{prefix}{n}"

# -----------------------------
# UI STATE (helpers simples)
# -----------------------------
def _read_ui_state() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    p = _external_ui_state_path()
    if p.exists():
        cfg.read(p, encoding="utf-8")
    return cfg


def _write_ui_state(cfg: configparser.ConfigParser) -> None:
    p = _external_ui_state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        cfg.write(f)


def get_ui_purchases_mode(default: str = "Compra") -> str:
    cfg = _read_ui_state()
    return cfg.get("purchases", "mode", fallback=default)


def set_ui_purchases_mode(mode: str) -> None:
    cfg = _read_ui_state()
    if "purchases" not in cfg:
        cfg["purchases"] = {}
    cfg["purchases"]["mode"] = str(mode)
    _write_ui_state(cfg)


# -----------------------------
# EMPRESA / TÉRMINOS
# -----------------------------
def get_company_info() -> Dict[str, Any]:
    cfg = read_config()
    sec = cfg["company"] if "company" in cfg else {}
    return {
        "name": sec.get("name", "Mi Empresa"),
        "rut": sec.get("rut", ""),
        "address": sec.get("address", ""),
        "phone": sec.get("phone", ""),
        "email": sec.get("email", ""),
        "logo": sec.get("logo", ""),
    }


def get_po_terms() -> str:
    cfg = read_config()
    return cfg.get("po", "footer_terms", fallback="Gracias por su preferencia.")


def get_po_payment_method() -> str:
    """
    Forma de pago por defecto para documentos (OC/Cotización).
    Se puede cambiar en config/settings.ini -> [po] payment_method = 'Crédito 30 días' | 'Efectivo' | ...
    """
    cfg = read_config()
    return cfg.get("po", "payment_method", fallback="Crédito 30 días")


# -----------------------------
# DESCARGAS / NOMBRES ÚNICOS
# -----------------------------
def get_downloads_dir() -> Path:
    """
    Resuelve la carpeta Descargas del usuario y la crea si no existe.
    """
    home = Path.home()

    if os.name == "nt":
        d = Path(os.environ.get("USERPROFILE", str(home))) / "Downloads"
    else:
        d = home / "Downloads"

    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        d = home

    return d


def unique_path(base_dir: Path, filename: str) -> Path:
    """
    Garantiza nombre único: <name> (1).ext, (2), ...
    """
    base_dir.mkdir(parents=True, exist_ok=True)
    p = base_dir / filename
    if not p.exists():
        return p

    stem = p.stem
    suffix = p.suffix
    i = 1
    while True:
        cand = base_dir / f"{stem} ({i}){suffix}"
        if not cand.exists():
            return cand
        i += 1


# -----------------------------
# INVENTARIO: LÍMITES / REFRESH
# -----------------------------
def get_inventory_limits() -> Tuple[int, int]:
    """
    Retorna (critical_min, critical_max) desde settings.ini, con defaults seguros.
    """
    cfg = read_config()
    sec = cfg["inventory"] if "inventory" in cfg else {}
    try:
        min_v = int(sec.get("critical_min", "5"))
    except Exception:
        min_v = 5
    try:
        max_v = int(sec.get("critical_max", "999999"))
    except Exception:
        max_v = 999_999
    if min_v < 0:
        min_v = 0
    if max_v < min_v:
        max_v = min_v
    return min_v, max_v


def set_inventory_limits(min_v: int, max_v: int) -> None:
    """
    Guarda límites críticos en settings.ini (normaliza valores).
    """
    if min_v < 0:
        min_v = 0
    if max_v < min_v:
        max_v = min_v

    cfg = read_config()
    if "inventory" not in cfg:
        cfg["inventory"] = {}
    cfg["inventory"]["critical_min"] = str(min_v)
    cfg["inventory"]["critical_max"] = str(max_v)
    write_config(cfg)


def get_inventory_refresh_ms() -> int:
    """
    Lee el intervalo de refresco (ms). Default: 3000 ms.
    """
    cfg = read_config()
    try:
        return int(cfg.get("inventory", "refresh_ms", fallback="3000"))
    except Exception:
        return 3000


def set_inventory_refresh_ms(ms: int) -> None:
    """
    Guarda el intervalo de refresco (ms). Mínimo 500 ms, máximo 60_000 ms.
    """
    ms = max(500, min(60_000, int(ms)))
    cfg = read_config()
    if "inventory" not in cfg:
        cfg["inventory"] = {}
    cfg["inventory"]["refresh_ms"] = str(ms)
    write_config(cfg)
