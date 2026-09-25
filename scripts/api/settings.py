"""
settings.py
Settings endpoints: model provider configuration (key never returned),
connection test, model listing, and the editable business profile.
"""

import time
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import ValidationError

from scripts.ai_extractor import build_request
from scripts.api.deps import get_profile_store, get_settings_store, require_admin, validation_messages
from scripts.business_profile import BusinessProfile, ProfileStore
from scripts.llm.providers import ProviderError
from scripts.llm.settings_store import (
    ModelSettings,
    ModelSettingsUpdate,
    SettingsStore,
    build_provider,
    presets_view,
    public_view,
)

router = APIRouter(prefix="/api", tags=["settings"])

TEST_LEAD = {
    "lead_id": "lead_connection_test",
    "source": "test",
    "contact": {"name": "Test Contact", "email": "test@example.com", "phone": None},
    "company": {"name": "Example Clinic", "website": None, "size": "11-50"},
    "message": "We run two clinics and want a chatbot to answer patient questions. Budget about 100,000 THB, live within 30 days.",
    "received_at": "2026-01-01T00:00:00Z",
}
NOT_CONFIGURED = "Choose a provider and a model first (and an API key if the provider needs one)."


def _preview(store: SettingsStore, update: ModelSettingsUpdate) -> ModelSettings:
    try:
        return store.preview(update)
    except ValidationError as err:
        raise HTTPException(status_code=422, detail=validation_messages(err))


@router.get("/providers")
def list_providers():
    return presets_view()


@router.get("/settings/model")
def get_model_settings(store: SettingsStore = Depends(get_settings_store)):
    return public_view(store.load())


@router.put("/settings/model", dependencies=[Depends(require_admin)])
def put_model_settings(update: ModelSettingsUpdate, store: SettingsStore = Depends(get_settings_store)):
    try:
        return public_view(store.save(update))
    except ValidationError as err:
        raise HTTPException(status_code=422, detail=validation_messages(err))


@router.post("/settings/model/test", dependencies=[Depends(require_admin)])
def test_model_settings(
    update: ModelSettingsUpdate = Body(default_factory=ModelSettingsUpdate),
    store: SettingsStore = Depends(get_settings_store),
    profile_store: ProfileStore = Depends(get_profile_store),
):
    """Runs one small extraction with the given (unsaved) settings."""
    settings = _preview(store, update)
    if not settings.is_configured:
        return {"ok": False, "error": NOT_CONFIGURED}
    started = time.perf_counter()
    try:
        result = build_provider(settings).extract(build_request(TEST_LEAD, profile_store.load(), settings))
    except ProviderError as err:
        return {"ok": False, "error": str(err), "latency_ms": round((time.perf_counter() - started) * 1000)}
    return {
        "ok": True,
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "model": settings.model,
        "sample": {
            "intent": result.get("intent"),
            "industry": result.get("industry"),
            "service": (result.get("service_match") or {}).get("offering"),
        },
    }


@router.post("/providers/models", dependencies=[Depends(require_admin)])
def list_provider_models(
    update: ModelSettingsUpdate = Body(default_factory=ModelSettingsUpdate),
    store: SettingsStore = Depends(get_settings_store),
):
    """Lists models the provider offers, using the given (unsaved) settings."""
    settings = _preview(store, update)
    if settings.preset.kind == "none":
        return {"models": [], "error": "Choose a provider first."}
    probe = settings if settings.model else settings.model_copy(update={"model": "probe"})
    if not probe.is_configured:
        return {"models": [], "error": "Add an API key first."}
    try:
        return {"models": build_provider(probe).list_models()}
    except ProviderError as err:
        return {"models": [], "error": str(err)}


@router.get("/settings/profile")
def get_profile(store: ProfileStore = Depends(get_profile_store)):
    return store.load().model_dump()


@router.put("/settings/profile", dependencies=[Depends(require_admin)])
def put_profile(body: Dict[str, Any] = Body(...), store: ProfileStore = Depends(get_profile_store)):
    try:
        profile = BusinessProfile(**body)
    except ValidationError as err:
        raise HTTPException(status_code=422, detail=validation_messages(err))
    return store.save(profile).model_dump()


@router.post("/settings/profile/reset", dependencies=[Depends(require_admin)])
def reset_profile(store: ProfileStore = Depends(get_profile_store)):
    return store.reset().model_dump()
