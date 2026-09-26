"""
insights.py
Read-only endpoints for the Dashboard (inbox aggregates) and the Trust page
(the conversion-model evaluation report produced by train_conversion_model.py).
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query

from scripts.api.deps import get_lead_store
from scripts.lead_store import MAX_STATS_DAYS, STATS_DAYS, LeadStore
from scripts.paths import ROOT_DIR

MODEL_REPORT_PATH = ROOT_DIR / "evaluation" / "models" / "conversion-model.json"

router = APIRouter(prefix="/api", tags=["insights"])


@router.get("/stats")
def get_stats(
    days: int = Query(STATS_DAYS, ge=1, le=MAX_STATS_DAYS),
    lead_store: LeadStore = Depends(get_lead_store),
):
    return lead_store.stats(days=days)


@router.get("/model/report")
def get_model_report():
    if not MODEL_REPORT_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="No model report yet. Run: python -m scripts.train_conversion_model",
        )
    return json.loads(MODEL_REPORT_PATH.read_text(encoding="utf-8"))
