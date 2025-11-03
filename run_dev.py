#!/usr/bin/env python
from __future__ import annotations

import os
import sys
import signal
import threading
import subprocess
from pathlib import Path


def which(cmd: str) -> str | None:
    from shutil import which as _which
    return _which(cmd)


ROOT = Path(__file__).resolve().parent
VERCEL_DIR = ROOT / "vercel"


def python_executable() -> str:
    win = os.name == "nt"
    venv_py = ROOT / (".venv/Scripts/python.exe" if win else ".venv/bin/python")
    if venv_py.exists():
        return str(venv_py)
    # fallback to current
    return sys.executable or ("python.exe" if win else "python3")


def npm_command() -> str:
    # On Windows npm is npm.cmd typically
    if os.name == "nt":
        return which("npm.cmd") or "npm.cmd"
    return which("npm") or "npm"


def popen_stream(cmd: list[str], cwd: Path | None, env: dict[str, str] | None, prefix: str):
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
        universal_newlines=True,
    )

    def _pump(stream, tag):
        if stream is None:
            return
        try:
            for line in stream:
                line = line.rstrip("\n")
                print(f"[{tag}] {line}")
        except Exception:
            pass

    th_out = threading.Thread(target=_pump, args=(proc.stdout, prefix), daemon=True)
    th_err = threading.Thread(target=_pump, args=(proc.stderr, prefix), daemon=True)
    th_out.start(); th_err.start()
    return proc


def main() -> int:
    print("Starting local dev servers: backend (FastAPI) and frontend (Next.js)\n")
    api_base = os.environ.get("NEXT_PUBLIC_API_BASE_URL", "http://127.0.0.1:8000")
    env_web = os.environ.copy()
    env_web.setdefault("NEXT_PUBLIC_API_BASE_URL", api_base)
    # A bit of color in some CLIs
    env_web.setdefault("FORCE_COLOR", "1")

    py = python_executable()
    uvicorn_cmd = [py, "-m", "uvicorn", "api.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"]

    npm = npm_command()
    web_cmd = [npm, "run", "dev"]

    # Launch both
    api_proc = popen_stream(uvicorn_cmd, ROOT, env_web, prefix="api")
    web_proc = popen_stream(web_cmd, VERCEL_DIR, env_web, prefix="web")

    print("\nBackend: http://127.0.0.1:8000  |  Frontend: http://127.0.0.1:3000\n")
    print("Press Ctrl+C to stop both processes.\n")

    # Graceful shutdown on Ctrl+C
    stop = threading.Event()

    def _handle_sigint(sig, frame):
        stop.set()
        # Terminate children
        for p in (api_proc, web_proc):
            try:
                if p.poll() is None:
                    p.terminate()
            except Exception:
                pass

    signal.signal(signal.SIGINT, _handle_sigint)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_sigint)

    # Wait loop: if one exits, stop the other
    try:
        while not stop.is_set():
            api_rc = api_proc.poll()
            web_rc = web_proc.poll()
            if api_rc is not None or web_rc is not None:
                break
            # Small sleep without importing time (use threading)
            stop.wait(0.25)
    finally:
        # Ensure both are terminated
        for p in (api_proc, web_proc):
            try:
                if p.poll() is None:
                    p.terminate()
            except Exception:
                pass
        for p in (api_proc, web_proc):
            try:
                p.wait(timeout=5)
            except Exception:
                pass

    api_rc = api_proc.poll()
    web_rc = web_proc.poll()
    if api_rc not in (None, 0):
        print(f"[api] exited with code {api_rc}")
    if web_rc not in (None, 0):
        print(f"[web] exited with code {web_rc}")
    # Return first non‑zero code if any
    for rc in (api_rc, web_rc):
        if rc and rc != 0:
            return int(rc)
    return 0


if __name__ == "__main__":
    sys.exit(main())

