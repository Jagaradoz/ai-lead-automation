"""
paths.py
Resolves repository and runtime data locations.
Runtime state (settings, business profile, lead database) lives in DATA_DIR,
which defaults to <repo>/data and is git-ignored.
"""

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = ROOT_DIR / "schemas"
CONFIG_DIR = ROOT_DIR / "config"
WEB_DIR = ROOT_DIR / "web"


def data_dir() -> Path:
    """Returns the runtime data directory, creating it on first use."""
    configured = os.environ.get("DATA_DIR")
    path = Path(configured).expanduser().resolve() if configured else ROOT_DIR / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path
