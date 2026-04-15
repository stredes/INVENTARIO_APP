from __future__ import annotations

import configparser
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SETTINGS_PATH = Path("config/settings.ini")
RELEASE_PATH = Path("config/release.json")
BUILD_INFO_PATH = Path("config/build_info.json")


def _frozen_dir() -> Path | None:
    try:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).parent
    except Exception:
        pass
    return None


def _candidate_paths(rel_path: Path) -> list[Path]:
    paths: list[Path] = []
    exedir = _frozen_dir()
    if exedir is not None:
        paths.append(exedir / rel_path)
    paths.append(Path.cwd() / rel_path)
    return paths


def _read_json(rel_path: Path) -> dict[str, Any]:
    for path in _candidate_paths(rel_path):
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
    return {}


def _read_company_name() -> str:
    cfg = configparser.ConfigParser()
    for path in _candidate_paths(SETTINGS_PATH):
        try:
            if path.exists():
                cfg.read(path, encoding="utf-8")
                break
        except Exception:
            continue
    return cfg.get("company", "name", fallback="InventarioApp")


@dataclass(frozen=True)
class AppMeta:
    app_name: str
    company_name: str
    version: str
    channel: str
    repo_owner: str
    repo_name: str
    release_tag: str
    portable_asset_pattern: str
    setup_asset_pattern: str

    @property
    def repo_slug(self) -> str:
        if self.repo_owner and self.repo_name:
            return f"{self.repo_owner}/{self.repo_name}"
        return ""


def get_app_meta() -> AppMeta:
    release_cfg = _read_json(RELEASE_PATH)
    build_info = _read_json(BUILD_INFO_PATH)

    app_name = str(build_info.get("app_name") or release_cfg.get("app_name") or "InventarioApp")
    company_name = str(build_info.get("company_name") or release_cfg.get("company_name") or _read_company_name())
    version = str(build_info.get("version") or release_cfg.get("base_version") or "0.1.0-dev")
    channel = str(build_info.get("channel") or release_cfg.get("release_channel") or "stable")
    repo_owner = str(build_info.get("repo_owner") or release_cfg.get("repo_owner") or "")
    repo_name = str(build_info.get("repo_name") or release_cfg.get("repo_name") or "")
    release_tag = str(build_info.get("release_tag") or f"v{version}")
    portable_asset_pattern = str(
        build_info.get("portable_asset_pattern")
        or release_cfg.get("portable_asset_pattern")
        or f"{app_name}-portable-*.zip"
    )
    setup_asset_pattern = str(
        build_info.get("setup_asset_pattern")
        or release_cfg.get("setup_asset_pattern")
        or f"{app_name}-setup-*.exe"
    )

    return AppMeta(
        app_name=app_name,
        company_name=company_name,
        version=version,
        channel=channel,
        repo_owner=repo_owner,
        repo_name=repo_name,
        release_tag=release_tag,
        portable_asset_pattern=portable_asset_pattern,
        setup_asset_pattern=setup_asset_pattern,
    )


def get_current_version() -> str:
    return get_app_meta().version
