from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from utils.app_metadata import (
    APP_EXECUTABLE_NAME,
    APP_NAME,
    APP_VERSION,
    DESKTOP_SHORTCUT_NAME,
    GITHUB_REPOSITORY,
    INSTALL_DIR_NAME,
    SETUP_ASSET_NAME,
)


GITHUB_API_BASE = "https://api.github.com"


@dataclass(slots=True)
class ReleaseInfo:
    version: str
    tag_name: str
    asset_name: str
    download_url: str
    html_url: str
    published_at: str
    body: str = ""


class UpdateService:
    @staticmethod
    def is_configured() -> bool:
        return bool(GITHUB_REPOSITORY and "/" in GITHUB_REPOSITORY)

    @staticmethod
    def is_frozen() -> bool:
        return bool(getattr(sys, "frozen", False))

    @staticmethod
    def get_latest_release() -> ReleaseInfo:
        if not UpdateService.is_configured():
            raise ValueError(
                "Debes configurar GITHUB_REPOSITORY en utils/app_metadata.py o en la variable de entorno FACTURION_GITHUB_REPOSITORY."
            )

        request = urllib.request.Request(
            f"{GITHUB_API_BASE}/repos/{GITHUB_REPOSITORY}/releases/latest",
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"{APP_NAME}/{APP_VERSION}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"No se pudo consultar el release más reciente: HTTP {error.code}") from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"No se pudo conectar con GitHub: {error.reason}") from error

        asset = next(
            (item for item in payload.get("assets", []) if item.get("name") == SETUP_ASSET_NAME),
            None,
        )
        if asset is None:
            raise RuntimeError(
                f"El release más reciente no contiene el instalador '{SETUP_ASSET_NAME}'."
            )

        return ReleaseInfo(
            version=UpdateService.normalize_version(payload.get("tag_name", "")),
            tag_name=payload.get("tag_name", ""),
            asset_name=asset["name"],
            download_url=asset["browser_download_url"],
            html_url=payload.get("html_url", ""),
            published_at=payload.get("published_at", ""),
            body=payload.get("body", "") or "",
        )

    @staticmethod
    def normalize_version(version: str) -> str:
        return version.strip().lstrip("vV")

    @staticmethod
    def parse_version(version: str) -> tuple[int, ...]:
        cleaned = UpdateService.normalize_version(version)
        parts = re.findall(r"\d+", cleaned)
        return tuple(int(part) for part in parts) if parts else (0,)

    @staticmethod
    def is_newer_version(candidate_version: str, current_version: str = APP_VERSION) -> bool:
        return UpdateService.parse_version(candidate_version) > UpdateService.parse_version(current_version)

    @staticmethod
    def download_installer(release: ReleaseInfo) -> Path:
        target_dir = Path(tempfile.mkdtemp(prefix="facturion_update_"))
        target_file = target_dir / release.asset_name
        request = urllib.request.Request(
            release.download_url,
            headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response, open(target_file, "wb") as output:
                output.write(response.read())
        except urllib.error.URLError as error:
            raise RuntimeError(f"No se pudo descargar el instalador: {error.reason}") from error
        return target_file

    @staticmethod
    def launch_updater(installer_path: Path, current_pid: int) -> None:
        script_path = installer_path.parent / "apply_update.ps1"
        install_exe = Path(os.getenv("ProgramFiles", r"C:\Program Files")) / INSTALL_DIR_NAME / APP_EXECUTABLE_NAME
        desktop_shortcut = f"{DESKTOP_SHORTCUT_NAME}.lnk"

        script_contents = f"""
$ErrorActionPreference = "Stop"
$installerPath = "{installer_path}"
$processId = {current_pid}
$installExe = "{install_exe}"
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "{desktop_shortcut}"

try {{
    Wait-Process -Id $processId -ErrorAction SilentlyContinue
}} catch {{
}}

Start-Sleep -Seconds 2

if (Test-Path $shortcutPath) {{
    Remove-Item -LiteralPath $shortcutPath -Force -ErrorAction SilentlyContinue
}}

Start-Process -FilePath $installerPath -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/TASKS=desktopicon' -Wait

if (Test-Path $installExe) {{
    $wsh = New-Object -ComObject WScript.Shell
    $shortcut = $wsh.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $installExe
    $shortcut.WorkingDirectory = Split-Path $installExe
    $shortcut.IconLocation = "$installExe,0"
    $shortcut.Save()
    Start-Process -FilePath $installExe
}}
"""
        script_path.write_text(script_contents.strip(), encoding="utf-8")

        creation_flags = getattr(subprocess, "DETACHED_PROCESS", 0x00000008) | getattr(
            subprocess,
            "CREATE_NEW_PROCESS_GROUP",
            0x00000200,
        )
        subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
            ],
            creationflags=creation_flags,
            close_fds=True,
        )
