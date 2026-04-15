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
from typing import Callable
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from src.app_meta import AppMeta, get_app_meta


API_BASE = "https://api.github.com/repos/{repo}/releases"


class UpdateProgressDialog(tk.Toplevel):
    def __init__(self, parent, *, title: str, message: str) -> None:
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.configure(padx=18, pady=16)

        wrapper = ttk.Frame(self)
        wrapper.pack(fill="both", expand=True)

        self.message_var = tk.StringVar(value=message)
        ttk.Label(
            wrapper,
            textvariable=self.message_var,
            justify="left",
            wraplength=340,
        ).pack(fill="x", pady=(0, 12))

        self.progress = ttk.Progressbar(wrapper, mode="determinate", length=320, maximum=100)
        self.progress.pack(fill="x")
        self.progress["value"] = 0

        self.status_var = tk.StringVar(value="Preparando...")
        ttk.Label(wrapper, textvariable=self.status_var, style="InfoBadge.TLabel").pack(
            anchor="w",
            pady=(12, 0),
        )

        self.update_idletasks()
        try:
            parent.update_idletasks()
            x = parent.winfo_rootx() + max((parent.winfo_width() - self.winfo_width()) // 2, 0)
            y = parent.winfo_rooty() + max((parent.winfo_height() - self.winfo_height()) // 2, 0)
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass
        try:
            self.grab_set()
        except Exception:
            pass

    def set_message(self, message: str, *, status: str | None = None) -> None:
        self.message_var.set(message)
        if status is not None:
            self.status_var.set(status)
        self.update_idletasks()

    def set_progress(self, current_bytes: int, total_bytes: int | None, *, status: str | None = None) -> None:
        current = max(0, int(current_bytes))
        total = int(total_bytes) if total_bytes and total_bytes > 0 else 0
        if total > 0:
            self.progress.configure(mode="determinate", maximum=total)
            self.progress["value"] = min(current, total)
            if status is None:
                status = f"{_format_mb(current)} / {_format_mb(total)}"
        else:
            self.progress.configure(mode="determinate", maximum=max(current, 1))
            self.progress["value"] = current
            if status is None:
                status = _format_mb(current)
        self.status_var.set(status or "Preparando...")
        self.update_idletasks()

    def close(self) -> None:
        try:
            self.progress.stop()
        except Exception:
            pass
        try:
            self.grab_release()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass


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


def _format_mb(value: int | float) -> str:
    return f"{(float(value) / (1024 * 1024)):.1f} MB"


def _release_from_payload(payload: dict, meta: AppMeta) -> ReleaseInfo | None:
    tag = str(payload.get("tag_name") or "")
    if not tag:
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
        tag=tag,
        name=str(payload.get("name") or ""),
        body=str(payload.get("body") or ""),
        portable_asset=portable_asset,
        setup_asset=setup_asset,
    )


def _fetch_latest_release(meta: AppMeta) -> ReleaseInfo | None:
    if not meta.repo_slug:
        return None
    req = urllib.request.Request(
        f"{API_BASE.format(repo=meta.repo_slug)}?per_page=10",
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

    if not isinstance(payload, list):
        return None

    candidates: list[ReleaseInfo] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        if item.get("draft") or item.get("prerelease"):
            continue
        release = _release_from_payload(item, meta)
        if release is None:
            continue
        if release.portable_asset is None and release.setup_asset is None:
            continue
        candidates.append(release)

    if not candidates:
        return None

    return max(candidates, key=lambda release: _version_key(release.tag))


def _write_update_script(target_dir: Path, extracted_dir: Path, current_exe: Path, app_name: str) -> Path:
    script_path = target_dir / "_apply_update.ps1"
    script = f"""
$ErrorActionPreference = 'Stop'
$targetDir = '{target_dir}'
$sourceDir = '{extracted_dir}'
$exePath = '{current_exe}'
$appName = '{app_name}'

Start-Sleep -Seconds 2

for ($i = 0; $i -lt 20; $i++) {{
  try {{
    Get-Process | Where-Object {{ $_.Path -eq $exePath }} | Stop-Process -Force -ErrorAction SilentlyContinue
  }} catch {{}}
  Start-Sleep -Milliseconds 500
}}

Get-ChildItem -LiteralPath $targetDir -Force | Where-Object {{
  $_.Name -notin @('_apply_update.ps1', '_update_payload', 'config', 'app_data')
}} | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Get-ChildItem -LiteralPath $sourceDir -Force | ForEach-Object {{
  if ($_.Name -in @('config', 'app_data')) {{
    return
  }}
  Copy-Item -LiteralPath $_.FullName -Destination $targetDir -Recurse -Force
}}
Remove-Item -LiteralPath $sourceDir -Recurse -Force -ErrorAction SilentlyContinue

try {{
  $shell = New-Object -ComObject WScript.Shell
  $desktopShortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) "$appName.lnk"
  $programsDir = Join-Path $env:APPDATA 'Microsoft\\Windows\\Start Menu\\Programs'
  $programShortcut = Join-Path $programsDir "$appName.lnk"
  foreach ($shortcutPath in @($desktopShortcut, $programShortcut)) {{
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $exePath
    $shortcut.WorkingDirectory = $targetDir
    $shortcut.IconLocation = "$exePath,0"
    $shortcut.Save()
  }}
}}
catch {{}}

Start-Process -FilePath $exePath
"""
    script_path.write_text(script.strip(), encoding="utf-8")
    return script_path


def _download_file(url: str, dest: Path, *, progress_cb: Callable[[int, int | None], None] | None = None) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "InventarioApp-updater"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        total_header = resp.headers.get("Content-Length")
        total_bytes = int(total_header) if total_header and str(total_header).isdigit() else None
        with dest.open("wb") as fh:
            downloaded = 0
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                fh.write(chunk)
                downloaded += len(chunk)
                if callable(progress_cb):
                    progress_cb(downloaded, total_bytes)


def _extract_zip_with_progress(
    zip_path: Path,
    extracted_dir: Path,
    *,
    progress_cb: Callable[[int, int], None] | None = None,
) -> None:
    with zipfile.ZipFile(zip_path, "r") as archive:
        members = [info for info in archive.infolist() if not info.is_dir()]
        total_bytes = sum(max(0, int(info.file_size or 0)) for info in members)
        extracted = 0
        for info in archive.infolist():
            archive.extract(info, extracted_dir)
            if not info.is_dir():
                extracted += max(0, int(info.file_size or 0))
                if callable(progress_cb):
                    progress_cb(extracted, total_bytes)

def _prepare_portable_update(
    release: ReleaseInfo,
    meta: AppMeta,
    *,
    download_progress_cb: Callable[[int, int | None], None] | None = None,
    install_progress_cb: Callable[[int, int], None] | None = None,
) -> Path:
    if release.portable_asset is None:
        raise RuntimeError("El release no incluye paquete portable.")
    if not getattr(sys, "frozen", False):
        raise RuntimeError("La actualización automática solo está disponible en la app instalada.")

    current_exe = Path(sys.executable).resolve()
    install_dir = current_exe.parent
    payload_dir = install_dir / "_update_payload"
    payload_dir.mkdir(parents=True, exist_ok=True)
    zip_path = payload_dir / release.portable_asset.name

    _download_file(
        release.portable_asset.download_url,
        zip_path,
        progress_cb=download_progress_cb,
    )

    extracted_dir = payload_dir / "portable"
    if extracted_dir.exists():
        shutil.rmtree(extracted_dir, ignore_errors=True)
    extracted_dir.mkdir(parents=True, exist_ok=True)

    _extract_zip_with_progress(
        zip_path,
        extracted_dir,
        progress_cb=install_progress_cb,
    )

    inner_dirs = [p for p in extracted_dir.iterdir() if p.is_dir()]
    source_root = inner_dirs[0] if len(inner_dirs) == 1 else extracted_dir
    return _write_update_script(install_dir, source_root, current_exe, meta.app_name)


def _launch_installation(script_path: Path) -> None:
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


def apply_release_update(root, release: ReleaseInfo | None) -> bool:
    if release is None or not release.tag:
        return False

    meta = get_app_meta()
    download_dialog = UpdateProgressDialog(
        root,
        title="Descargando actualizaci?n",
        message=(
            f"Descargando la versi?n {release.tag}.\n"
            "Mant?n esta ventana abierta hasta que finalice la descarga."
        ),
    )
    download_dialog.set_message(
        (
            f"Descargando la versi?n {release.tag}.\n"
            "Mant?n esta ventana abierta hasta que finalice la descarga."
        ),
        status="0.0 MB / 0.0 MB",
    )

    def _worker() -> None:
        install_dialog_box: dict[str, UpdateProgressDialog] = {}
        install_dialog_ready = threading.Event()

        try:
            def _update_download(current: int, total: int | None) -> None:
                try:
                    root.after(
                        0,
                        lambda c=current, t=total: download_dialog.set_progress(
                            c,
                            t,
                            status=f"Descargando: {_format_mb(c)} / {_format_mb(t or c)}",
                        ),
                    )
                except Exception:
                    pass

            def _create_install_dialog() -> None:
                install_dialog = UpdateProgressDialog(
                    root,
                    title="Instalando actualizaci?n",
                    message=(
                        f"La versi?n {release.tag} ya fue descargada.\n"
                        "Preparando la instalaci?n."
                    ),
                )
                install_dialog.set_progress(0, 1, status="Preparando instalaci?n...")
                install_dialog_box["dialog"] = install_dialog
                install_dialog_ready.set()

            def _update_install(current: int, total: int) -> None:
                install_dialog_ready.wait(10)
                try:
                    root.after(
                        0,
                        lambda c=current, t=total: install_dialog_box["dialog"].set_progress(
                            c,
                            t,
                            status=f"Instalando: {_format_mb(c)} / {_format_mb(t)}",
                        ),
                    )
                except Exception:
                    pass

            root.after(0, _create_install_dialog)
            script_path = _prepare_portable_update(
                release,
                meta,
                download_progress_cb=_update_download,
                install_progress_cb=_update_install,
            )
        except Exception as ex:
            def _fail() -> None:
                download_dialog.close()
                try:
                    dialog = install_dialog_box.get("dialog")
                    if dialog is not None:
                        dialog.close()
                except Exception:
                    pass
                try:
                    messagebox.showwarning(
                        "Actualizaci?n",
                        (
                            f"Hay una nueva versi?n disponible ({release.tag}), "
                            "pero no se pudo aplicar autom?ticamente.\n\n"
                            f"Detalle: {ex}"
                        ),
                        parent=root,
                    )
                except Exception:
                    pass

            try:
                root.after(0, _fail)
            except Exception:
                pass
            return

        def _install() -> None:
            download_dialog.close()
            install_dialog = install_dialog_box.get("dialog")
            if install_dialog is None:
                install_dialog = UpdateProgressDialog(
                    root,
                    title="Instalando actualizaci?n",
                    message=(
                        f"La versi?n {release.tag} ya fue descargada.\n"
                        "La aplicaci?n se cerrar? para completar la instalaci?n."
                    ),
                )
            install_dialog.set_message(
                (
                    f"La versi?n {release.tag} ya fue descargada.\n"
                    "La aplicaci?n se cerrar? para completar la instalaci?n."
                ),
                status="Instalaci?n preparada. Cerrando app...",
            )
            install_dialog.set_progress(1, 1, status="Instalaci?n preparada. Cerrando app...")

            def _start_install() -> None:
                try:
                    _launch_installation(script_path)
                finally:
                    root.after(250, root.destroy)

            root.after(900, _start_install)

        try:
            root.after(0, _install)
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()
    return True


def check_for_updates_async(root, *, on_update_ready=None, on_check_complete=None, auto_apply: bool = False) -> None:
    meta = get_app_meta()

    def _worker() -> None:
        release = _fetch_latest_release(meta)

        def _on_main_thread() -> None:
            if release is not None and release.tag and _is_newer(release.tag, meta.version):
                if callable(on_update_ready):
                    try:
                        on_update_ready(release)
                    except Exception:
                        pass
                if auto_apply:
                    apply_release_update(root, release)
            if callable(on_check_complete):
                try:
                    on_check_complete(release)
                except Exception:
                    pass

        try:
            root.after(0, _on_main_thread)
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()
