"""
leads.py
Lead endpoints: process (normalize → analyze → score → save), the inbox listing,
detail, status/notes updates, rescore, re-analyze, delete and CSV export.
"""

import time
from typing import Any, Dict, Literal, Optional, Tuple

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from jsonschema import ValidationError as SchemaError
from pydantic import BaseModel, Field

from scripts.ai_extractor import ModelUnavailableError, run_analysis
from scripts.api.deps import get_lead_store, get_profile_store, get_settings_store
from scripts.business_profile import ProfileStore
from scripts.dispatch import build_hubspot_payload, build_slack_alert, run_live_sync
from scripts.lead_store import MAX_NOTES_CHARS, PRIORITIES, STATUSES, LeadStore
from scripts.llm.settings_store import SettingsStore
from scripts.normalize import normalize_lead
from scripts.scoring_engine import score_lead

MAX_MESSAGE_CHARS = 20000

router = APIRouter(prefix="/api/leads", tags=["leads"])


class LeadPatch(BaseModel):
    status: Optional[Literal[STATUSES]] = None  # type: ignore[valid-type]
    notes: Optional[str] = Field(None, max_length=MAX_NOTES_CHARS)


def _normalize(body: Dict[str, Any]) -> Dict[str, Any]:
    try:
        lead = normalize_lead(body)
    except SchemaError as err:
        raise HTTPException(status_code=422, detail=f"The lead is missing required fields: {err.message}")
    message = (lead.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=422, detail="The lead has no message to analyze.")
    if len(message) > MAX_MESSAGE_CHARS:
        raise HTTPException(status_code=422, detail=f"Messages are limited to {MAX_MESSAGE_CHARS:,} characters.")
    return lead


def _analyze_and_score(
    lead: Dict[str, Any], settings_store: SettingsStore, profile_store: ProfileStore
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    profile = profile_store.load()
    try:
        analysis, meta = run_analysis(lead, profile, settings_store.load())
    except ModelUnavailableError as err:
        raise HTTPException(status_code=502, detail=f"The model could not analyze this lead: {err}")
    return analysis, score_lead(lead, analysis, profile), meta


def _get_or_404(store: LeadStore, lead_id: int) -> Dict[str, Any]:
    record = store.find_by_id(lead_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Lead not found.")
    return record


@router.post("/normalize")
def normalize_endpoint(body: Dict[str, Any] = Body(...)):
    """Normalizes any raw channel payload into a Canonical Lead without analyzing it."""
    try:
        return normalize_lead(body)
    except SchemaError as err:
        raise HTTPException(status_code=422, detail=f"Normalization failed: {err.message}")


@router.post("/process")
def process_lead(
    body: Dict[str, Any] = Body(...),
    save: bool = Query(True),
    live_sync: bool = Query(False),
    settings_store: SettingsStore = Depends(get_settings_store),
    profile_store: ProfileStore = Depends(get_profile_store),
    lead_store: LeadStore = Depends(get_lead_store),
):
    """Normalize → analyze (model or rules) → score → optionally save and dispatch."""
    started = time.perf_counter()
    lead = _normalize(body)
    analysis, score, meta = _analyze_and_score(lead, settings_store, profile_store)
    record = lead_store.create(lead, analysis, score, meta) if save else None

    hubspot = build_hubspot_payload(lead, analysis, score)
    slack = build_slack_alert(lead, analysis, score)
    live_results = run_live_sync(hubspot, slack) if live_sync else {}

    return {
        "status": "success",
        "id": record["id"] if record else None,
        "execution_time_ms": round((time.perf_counter() - started) * 1000, 2),
        "lead": lead,
        "analysis": analysis,
        "score": score,
        "meta": meta,
        "dispatch": {
            "hubspot": hubspot,
            "slack": slack,
            "live_sync_executed": bool(live_results),
            "live_sync_results": live_results,
        },
    }


@router.post("/rescore-all")
def rescore_all(
    profile_store: ProfileStore = Depends(get_profile_store),
    lead_store: LeadStore = Depends(get_lead_store),
):
    """Re-applies the current scoring rules to every saved lead. No model calls."""
    profile = profile_store.load()
    count = 0
    for lead_id in lead_store.all_ids():
        record = lead_store.find_by_id(lead_id)
        if record is None:
            continue
        score = score_lead(record["lead"], record["analysis"], profile)
        lead_store.replace_result(lead_id, record["analysis"], score, record["meta"])
        count += 1
    return {"rescored": count}


@router.get("")
def list_leads(
    priority: Optional[Literal[PRIORITIES]] = None,  # type: ignore[valid-type]
    status: Optional[Literal[STATUSES]] = None,  # type: ignore[valid-type]
    q: Optional[str] = Query(None, max_length=200),
    sort: Literal["recent", "score"] = "recent",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    lead_store: LeadStore = Depends(get_lead_store),
):
    return lead_store.find_all(priority=priority, status=status, q=q, sort=sort, limit=limit, offset=offset)


@router.get("/export.csv")
def export_csv(lead_store: LeadStore = Depends(get_lead_store)):
    return StreamingResponse(
        lead_store.iter_csv(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="leads.csv"'},
    )


@router.get("/{lead_id}")
def get_lead(lead_id: int, lead_store: LeadStore = Depends(get_lead_store)):
    return _get_or_404(lead_store, lead_id)


@router.patch("/{lead_id}")
def update_lead(lead_id: int, patch: LeadPatch, lead_store: LeadStore = Depends(get_lead_store)):
    record = lead_store.update(lead_id, status=patch.status, notes=patch.notes)
    if record is None:
        raise HTTPException(status_code=404, detail="Lead not found.")
    return record


@router.delete("/{lead_id}", status_code=204)
def delete_lead(lead_id: int, lead_store: LeadStore = Depends(get_lead_store)):
    if not lead_store.delete(lead_id):
        raise HTTPException(status_code=404, detail="Lead not found.")
    return Response(status_code=204)


@router.post("/{lead_id}/rescore")
def rescore_lead(
    lead_id: int,
    profile_store: ProfileStore = Depends(get_profile_store),
    lead_store: LeadStore = Depends(get_lead_store),
):
    """Re-applies the current scoring rules to the stored analysis. No model call."""
    record = _get_or_404(lead_store, lead_id)
    score = score_lead(record["lead"], record["analysis"], profile_store.load())
    return lead_store.replace_result(lead_id, record["analysis"], score, record["meta"])


@router.post("/{lead_id}/reanalyze")
def reanalyze_lead(
    lead_id: int,
    settings_store: SettingsStore = Depends(get_settings_store),
    profile_store: ProfileStore = Depends(get_profile_store),
    lead_store: LeadStore = Depends(get_lead_store),
):
    """Runs extraction again with the current model and rules."""
    record = _get_or_404(lead_store, lead_id)
    analysis, score, meta = _analyze_and_score(record["lead"], settings_store, profile_store)
    return lead_store.replace_result(lead_id, analysis, score, meta)
