"""
test_insights.py
Dashboard stats, follow-up routing/drafts, the model report endpoint and demo seeding.
"""

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from scripts.business_profile import load_default_profile
from scripts.followup import REVIEW_OWNER, build_followup, route_lead
from scripts.lead_store import LeadStore
from scripts.paths import ROOT_DIR, data_dir
from scripts.seed_demo_leads import clear_demo, seed
from scripts.serve_api import app


@pytest.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as c:
        yield c


@pytest.fixture
def lead_payload():
    with open(ROOT_DIR / "examples" / "normalized-lead.json", encoding="utf-8") as f:
        return json.load(f)


def _store() -> LeadStore:
    return LeadStore(data_dir() / "leads.db")


def _analysis(language="en", **overrides):
    base = {
        "language": language,
        "budget": {"stated": False, "amount": None, "currency": None},
        "timeline_days": None,
        "contact_role": None,
        "service_requested": "chatbot",
        "service_match": {"offering": "AI chatbot for customer questions", "tier": "core"},
    }
    return {**base, **overrides}


def _lead(name="Ann", email=None, company=None):
    return {"contact": {"name": name, "email": email, "phone": None}, "company": {"name": company}}


# ---------- stats ----------

def test_stats_counts_priorities_sources_and_win_rate():
    store = _store()
    lead = {"lead_id": "x", "source": "line", "contact": {"name": "A"}, "company": {}, "message": "hi"}
    score_hi = {"total_score": 90, "priority": "high"}
    score_lo = {"total_score": 20, "priority": "low"}
    store.create(lead, {}, score_hi, {"latency_ms": 100}, status="won")
    store.create(lead, {}, score_hi, {"latency_ms": 300}, status="lost")
    store.create({**lead, "source": "website"}, {}, score_lo, {}, status="won")

    stats = store.stats(days=7)

    assert stats["total"] == 3
    assert stats["by_priority"] == {"high": 2, "medium": 0, "low": 1, "disqualified": 0}
    assert stats["win_rate"] == pytest.approx(2 / 3, abs=0.001)
    assert stats["median_latency_ms"] == 200
    line = next(s for s in stats["by_source"] if s["source"] == "line")
    assert line == {"source": "line", "count": 2, "won": 1, "closed": 2, "win_rate": 0.5, "avg_score": 90.0}
    assert len(stats["daily"]) == 7
    assert stats["daily"][-1]["count"] == 3


def test_stats_daily_window_excludes_old_leads():
    store = _store()
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    lead = {"lead_id": "x", "source": "email", "contact": {"name": "A"}, "company": {}, "message": "hi"}
    store.create(lead, {}, {"total_score": 50, "priority": "medium"}, {}, created_at=old)

    stats = store.stats(days=7)

    assert stats["total"] == 1
    assert sum(d["count"] for d in stats["daily"]) == 0
    assert stats["win_rate"] is None


def test_create_rejects_unknown_status():
    with pytest.raises(ValueError):
        _store().create({"contact": {}}, {}, {"priority": "low"}, {}, status="bogus")


@pytest.mark.anyio
async def test_stats_endpoint(client, lead_payload):
    await client.post("/api/leads/process", json=lead_payload)
    resp = await client.get("/api/stats", params={"days": 14})
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert (await client.get("/api/stats", params={"days": 0})).status_code == 422


# ---------- follow-up ----------

def test_route_by_priority_and_review_override():
    assert route_lead({"priority": "high"})["respond_within_min"] == 60
    assert route_lead({"priority": "high", "requires_human_review": True})["owner"] == REVIEW_OWNER
    assert route_lead({"priority": "disqualified", "requires_human_review": True})["owner"] == "No owner"
    assert route_lead({})["priority"] == "disqualified"


def test_english_draft_asks_for_missing_details():
    result = build_followup(_lead(), _analysis(), {"priority": "medium"}, load_default_profile())
    body = result["reply"]["body"]
    assert body.startswith("Hi Ann,")
    assert "AI chatbot for customer questions" in body
    assert "budget" in body and "live" in body
    assert body.count("\n- ") == 3


def test_thai_draft_and_no_questions_when_complete():
    analysis = _analysis(
        language="th", budget={"stated": True, "amount": 1, "currency": "THB"}, timeline_days=10, contact_role="owner"
    )
    reply = build_followup(_lead("สมชาย", "a@b.example", "ร้าน"), analysis, {"priority": "high"}, load_default_profile())["reply"]
    assert reply["language"] == "th"
    assert reply["body"].startswith("สวัสดีครับ/ค่ะ คุณสมชาย")
    assert "- " not in reply["body"]


def test_disqualified_gets_no_reply():
    assert build_followup(_lead(), _analysis(), {"priority": "disqualified"}, load_default_profile())["reply"] is None


@pytest.mark.anyio
async def test_followup_endpoint(client, lead_payload):
    lead_id = (await client.post("/api/leads/process", json=lead_payload)).json()["id"]
    resp = await client.get(f"/api/leads/{lead_id}/followup")
    assert resp.status_code == 200
    assert {"route", "reply"} <= resp.json().keys()
    assert (await client.get("/api/leads/9999/followup")).status_code == 404


# ---------- model report ----------

@pytest.mark.anyio
async def test_model_report_endpoint(client, monkeypatch, tmp_path):
    from scripts.api import insights

    missing = tmp_path / "none.json"
    monkeypatch.setattr(insights, "MODEL_REPORT_PATH", missing)
    assert (await client.get("/api/model/report")).status_code == 404

    missing.write_text(json.dumps({"best_model": "x"}), encoding="utf-8")
    resp = await client.get("/api/model/report")
    assert resp.status_code == 200
    assert resp.json()["best_model"] == "x"


def test_committed_model_report_is_complete():
    report = json.loads((ROOT_DIR / "evaluation" / "models" / "conversion-model.json").read_text(encoding="utf-8"))
    for key in ("dataset", "models", "roc", "calibration", "lift", "feature_importance", "best_model"):
        assert key in report
    best = next(m for m in report["models"] if m["key"] == report["best_model"])
    baseline = next(m for m in report["models"] if m["key"] == "baseline")
    assert best["roc_auc"] > baseline["roc_auc"]


# ---------- demo seeding ----------

def test_seed_tags_backdates_and_clears():
    store = _store()
    items = [
        {"source": "line", "name": "A", "company": "Clinic", "email": "a@x.example", "phone": None,
         "size": "11-50", "message": "Need a chatbot, budget 100,000 THB, within 30 days."},
        {"source": "website", "name": "Spam", "company": None, "email": None, "phone": None,
         "size": None, "message": "Buy 500 backlinks for 49 USD"},
    ]
    assert seed(items, store) == 2
    records = [store.find_by_id(i) for i in store.all_ids()]
    assert all(r["meta"]["demo"] for r in records)

    store.create(records[0]["lead"], records[0]["analysis"], records[0]["score"], {"engine": "rules"})
    assert clear_demo(store) == 2
    assert len(store.all_ids()) == 1
