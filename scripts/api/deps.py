"""
deps.py
Shared FastAPI dependencies: storage handles and the optional admin guard.
Stores resolve DATA_DIR at call time so tests (and deployments) can relocate it.
"""

import hmac
import os
from functools import lru_cache
from typing import List, Optional

from fastapi import Header, HTTPException
from pydantic import ValidationError

from scripts.business_profile import ProfileStore
from scripts.lead_store import LeadStore
from scripts.llm.settings_store import SettingsStore
from scripts.paths import data_dir


def get_settings_store() -> SettingsStore:
    return SettingsStore()


def get_profile_store() -> ProfileStore:
    return ProfileStore()


@lru_cache(maxsize=8)
def _lead_store(path: str) -> LeadStore:
    from pathlib import Path

    return LeadStore(Path(path))


def get_lead_store() -> LeadStore:
    return _lead_store(str(data_dir() / "leads.db"))


def require_admin(authorization: Optional[str] = Header(None)) -> None:
    """When ADMIN_TOKEN is set, settings writes need `Authorization: Bearer <token>`."""
    token = os.environ.get("ADMIN_TOKEN")
    if not token:
        return
    expected = f"Bearer {token}".encode()
    if not authorization or not hmac.compare_digest(authorization.encode(), expected):
        raise HTTPException(status_code=401, detail="Enter the admin token to change settings.")


def validation_messages(err: ValidationError) -> str:
    """Flattens a pydantic error into one readable sentence list for the UI."""
    parts: List[str] = []
    for item in err.errors():
        where = ".".join(str(p) for p in item.get("loc", ()) if p != "__root__")
        message = item.get("msg", "Invalid value").removeprefix("Value error, ")
        parts.append(f"{where}: {message}" if where else message)
    return "; ".join(parts)
