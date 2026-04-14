from __future__ import annotations

import os
import sys
from pathlib import Path

from utils.app_metadata import APP_NAME


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_runtime_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return get_project_root()


def get_user_data_dir() -> Path:
    if os.name == "nt":
        local_app_data = os.getenv("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / APP_NAME
    return get_project_root() / "data"


def get_database_dir() -> Path:
    if getattr(sys, "frozen", False):
        return get_user_data_dir() / "data"
    return get_project_root() / "data"


def get_backup_dir() -> Path:
    if getattr(sys, "frozen", False):
        return get_user_data_dir() / "backups"
    return get_project_root() / "backups"
