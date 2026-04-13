from __future__ import annotations

import fnmatch
import json
import shutil
import subprocess
import sys
import threading
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox

from src.app_meta import AppMeta, get_app_meta


API_BASE = "https://api.github.com/repos/{repo}/releases/latest"


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    download_url: str


@dataclass(frozen=True)
class ReleaseInfo:
    tag: str
    name: str
    body: str
    portable_asset: ReleaseAsset | None
    setup_asset: ReleaseAsset | None


def _version_key(value: str) -> tuple[int, ...]:
    cleaned = value.strip().lower().lstrip("v").replace("-", ".").replace("_", ".")
    numbers: list[int] = []
    for part in cleaned.split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        if digits:
            numbers.append(int(digits))
    return tuple(numbers or [0])


def _is_newer(remote_tag: str, current_version: str) -> bool:
    return _version_key(remote_tag) > _version_key(current_version)


def _fetch_latest_release(meta: AppMeta) -> ReleaseInfo | None:
    if not meta.repo_slug:
        return None
    req = urllib.request.Request(
        API_BASE.format(repo=meta.repo_slug),
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{meta.app_name}-updater",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    assets = payload.get("assets", []) or []
    portable_asset = None
    setup_asset = None
    for asset in assets:
        name = str(asset.get("name") or "")
        dl = str(asset.get("browser_download_url") or "")
        if not name or not dl:
            continue
        if portable_asset is None and fnmatch.fnmatch(name, meta.portable_asset_pattern):
            portable_asset = ReleaseAsset(name=name, download_url=dl)
        if setup_asset is None and fnmatch.fnmatch(name, meta.setup_asset_pattern):
            setup_asset = ReleaseAsset(name=name, download_url=dl)

    return ReleaseInfo(
        tag=str(payload.get("tag_name") or ""),
        name=str(payload.get("name") or ""),
        body=str(payload.get("body") or ""),
        portable_asset=portable_asset,
        setup_asset=setup_asset,
    )


def _write_update_script(target_dir: Path, extracted_dir: Path, current_exe: Path) -> Path:
    script_path = target_dir / "_apply_update.ps1"
    script = f"""
$ErrorActionPreference = 'Stop'
$targetDir = '{target_dir}'
$sourceDir = '{extracted_dir}'
$exePath = '{current_exe}'

Start-Sleep -Seconds 2

for ($i = 0; $i -lt 20; $i++) {{
  try {{
    Get-Process | Where-Object {{ $_.Path -eq $exePath }} | Stop-Process -Force -ErrorAction SilentlyContinue
  }} catch {{}}
  Start-Sleep -Milliseconds 500
}}

Get-ChildItem -LiteralPath $targetDir -Force | Where-Object {{
  $_.Name -notin @('_apply_update.ps1', '_update_payload')
}} | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Copy-Item -LiteralPath (Join-Path $sourceDir '*') -Destination $targetDir -Recurse -Force
Remove-Item -LiteralPath $sourceDir -Recurse -Force -ErrorAction SilentlyContinue
Start-Process -FilePath $exePath
"""
    script_path.write_text(script.strip(), encoding="utf-8")
    return script_path


def _download_file(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "InventarioApp-updater"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        with dest.open("wb") as fh:
            shutil.copyfileobj(resp, fh)


def _apply_portable_update(root, release: ReleaseInfo, meta: AppMeta) -> None:
    if release.portable_asset is None:
        return
    if not getattr(sys, "frozen", False):
        return

    current_exe = Path(sys.executable).resolve()
    install_dir = current_exe.parent
    payload_dir = install_dir / "_update_payload"
    payload_dir.mkdir(parents=True, exist_ok=True)
    zip_path = payload_dir / release.portable_asset.name

    _download_file(release.portable_asset.download_url, zip_path)

    extracted_dir = payload_dir / "portable"
    if extracted_dir.exists():
        shutil.rmtree(extracted_dir, ignore_errors=True)
    extracted_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(extracted_dir)

    inner_dirs = [p for p in extracted_dir.iterdir() if p.is_dir()]
    source_root = inner_dirs[0] if len(inner_dirs) == 1 else extracted_dir
    script_path = _write_update_script(install_dir, source_root, current_exe)

    messagebox.showinfo(
        "Actualización disponible",
        f"Se descargó {release.tag}. La aplicación se reiniciará para aplicar la actualización.",
        parent=root,
    )
    subprocess.Popen(
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
        ],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    root.after(150, root.destroy)


def apply_release_update(root, release: ReleaseInfo | None) -> bool:
    if release is None or not release.tag:
        return False
    meta = get_app_meta()
    try:
        _apply_portable_update(root, release, meta)
        return True
    except Exception:
        try:
            messagebox.showwarning(
                "Actualización",
                f"Hay una nueva versión disponible ({release.tag}), pero no se pudo aplicar automáticamente.",
                parent=root,
            )
        except Exception:
            pass
        return False


def check_for_updates_async(root, *, on_update_ready=None, auto_apply: bool = False) -> None:
    meta = get_app_meta()

    def _worker() -> None:
        release = _fetch_latest_release(meta)
        if release is None or not release.tag:
            return
        if not _is_newer(release.tag, meta.version):
            return

        def _on_main_thread() -> None:
            if callable(on_update_ready):
                try:
                    on_update_ready(release)
                except Exception:
                    pass
            if auto_apply:
                apply_release_update(root, release)

        try:
            root.after(0, _on_main_thread)
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()
