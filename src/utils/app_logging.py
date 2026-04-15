from __future__ import annotations

import atexit
import faulthandler
import logging
import os
import sys
import threading
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import FrameType
from typing import Any


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_LOG_DIR = _PROJECT_ROOT / "app_data" / "logs"
_MAIN_LOG = _LOG_DIR / "app.log"
_TRACE_LOG = _LOG_DIR / "trace.log"

_TRACE_INSTALLED = False
_LOOP_LINE_CACHE: dict[str, dict[int, str]] = {}


def _ensure_log_dir() -> Path:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    return _LOG_DIR


def get_log_dir() -> Path:
    return _ensure_log_dir()


def get_known_log_files() -> list[Path]:
    base = _ensure_log_dir()
    files = [base / "app.log", base / "trace.log", base / "crash.log"]
    return files


def _short(value: Any, max_len: int = 180) -> str:
    try:
        text = repr(value)
    except Exception:
        text = f"<unrepr {type(value).__name__}>"
    if len(text) > max_len:
        return text[: max_len - 3] + "..."
    return text


def _is_project_file(filename: str | None) -> bool:
    if not filename:
        return False
    try:
        path = Path(filename).resolve()
    except Exception:
        return False
    if path == Path(__file__).resolve():
        return False
    try:
        path.relative_to(_PROJECT_ROOT)
    except Exception:
        return False
    return path.suffix.lower() == ".py"


def _get_loop_source(filename: str, lineno: int) -> str | None:
    cache = _LOOP_LINE_CACHE.get(filename)
    if cache is None:
        cache = {}
        _LOOP_LINE_CACHE[filename] = cache
    if lineno in cache:
        return cache[lineno]
    try:
        line = Path(filename).read_text(encoding="utf-8", errors="ignore").splitlines()[lineno - 1].strip()
    except Exception:
        line = ""
    if line.startswith("for ") or line.startswith("while "):
        cache[lineno] = line
        return line
    cache[lineno] = ""
    return None


def _trace_callback(frame: FrameType, event: str, arg: Any):
    filename = frame.f_code.co_filename
    if not _is_project_file(filename):
        return _trace_callback

    logger = logging.getLogger("inventario.trace")
    code = frame.f_code
    func_name = f"{Path(filename).name}:{code.co_name}"

    if event == "call":
        logger.debug("CALL %s:%s %s", Path(filename).name, frame.f_lineno, func_name)
        return _trace_callback

    if event == "return":
        logger.debug("RETURN %s -> %s", func_name, _short(arg))
        return _trace_callback

    if event == "exception":
        exc_type, exc_value, _tb = arg
        logger.exception(
            "EXCEPTION %s:%s %s -> %s: %s",
            Path(filename).name,
            frame.f_lineno,
            func_name,
            getattr(exc_type, "__name__", str(exc_type)),
            exc_value,
        )
        return _trace_callback

    if event == "line":
        loop_src = _get_loop_source(filename, frame.f_lineno)
        if loop_src:
            logger.debug("LOOP %s:%s %s", Path(filename).name, frame.f_lineno, loop_src)
        return _trace_callback

    return _trace_callback


def _install_fault_handler() -> None:
    try:
        fault_file = (_ensure_log_dir() / "crash.log").open("a", encoding="utf-8")
        faulthandler.enable(file=fault_file, all_threads=True)
        atexit.register(fault_file.close)
    except Exception:
        pass


def _install_exception_hooks() -> None:
    logger = logging.getLogger("inventario")

    def _sys_hook(exc_type, exc_value, exc_tb):
        logger.critical("Excepcion no controlada", exc_info=(exc_type, exc_value, exc_tb))
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    def _thread_hook(args):
        logger.critical(
            "Excepcion no controlada en hilo %s",
            getattr(args.thread, "name", "unknown"),
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = _sys_hook
    threading.excepthook = _thread_hook


def _install_trace_hooks() -> None:
    global _TRACE_INSTALLED
    if _TRACE_INSTALLED:
        return
    sys.settrace(_trace_callback)
    threading.settrace(_trace_callback)
    _TRACE_INSTALLED = True


def attach_tk_exception_logger(root: Any) -> None:
    logger = logging.getLogger("inventario.tk")

    def _report_callback_exception(exc_type, exc_value, exc_tb):
        logger.exception(
            "Excepcion no controlada en callback Tk",
            exc_info=(exc_type, exc_value, exc_tb),
        )
        try:
            traceback.print_exception(exc_type, exc_value, exc_tb)
        except Exception:
            pass

    try:
        root.report_callback_exception = _report_callback_exception
    except Exception:
        logger.exception("No se pudo instalar report_callback_exception")


def configure_global_logging(*, enable_trace: bool = True) -> None:
    _ensure_log_dir()

    root_logger = logging.getLogger()
    if getattr(root_logger, "_inventario_logging_ready", False):
        return

    root_logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    app_handler = RotatingFileHandler(_MAIN_LOG, maxBytes=4_000_000, backupCount=4, encoding="utf-8")
    app_handler.setLevel(logging.DEBUG)
    app_handler.setFormatter(formatter)

    trace_handler = RotatingFileHandler(_TRACE_LOG, maxBytes=6_000_000, backupCount=4, encoding="utf-8")
    trace_handler.setLevel(logging.DEBUG)
    trace_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    root_logger.addHandler(app_handler)
    root_logger.addHandler(console_handler)

    trace_logger = logging.getLogger("inventario.trace")
    trace_logger.setLevel(logging.DEBUG)
    trace_logger.addHandler(trace_handler)
    trace_logger.propagate = False

    for name in ("urllib3", "PIL"):
        logging.getLogger(name).setLevel(logging.WARNING)

    setattr(root_logger, "_inventario_logging_ready", True)
    _install_fault_handler()
    _install_exception_hooks()

    logging.getLogger("inventario").info("Logging inicializado en %s", _LOG_DIR)
    if enable_trace and os.getenv("INVENTARIO_DISABLE_TRACE", "").strip() != "1":
        _install_trace_hooks()
        logging.getLogger("inventario").info("Trace global de funciones y ciclos activado")
