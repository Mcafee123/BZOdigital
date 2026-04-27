"""Resolve the runtime data directory.

Local dev (`uv run uvicorn` from `app/`): falls back to `<repo_root>/data`,
which is where `bzo.db` lives in the git tree.

Production (Azure Container Apps): Terraform sets `DATA_PATH=/mnt/repo/data`,
pointing at the Azure File share mounted at `var.mount_path`.
"""
from __future__ import annotations

import os
from pathlib import Path

# paths.py -> app -> nupla -> src -> <repo_root>
_REPO_DATA = Path(__file__).resolve().parents[3] / "data"


def get_data_path() -> Path:
    """Return the base directory holding `bzo.db` and other runtime data."""
    return Path(os.environ.get("DATA_PATH", _REPO_DATA))
