"""
test_api_inbox.py
Integration tests for the lead inbox API: process + persist, list, detail,
status updates, rescore/reanalyze, delete, CSV export, and model fallback behaviour.
"""

import json

import httpx
import pytest

from scripts.paths import ROOT_DIR
from scripts.serve_api import app

UNREACHABLE_MODEL = {
    "provider": "custom",
    "base_url": "http://127.0.0.1:9/v1",
    "model": "nothing-here",
    "timeout_s": 5,
}


@pytest.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as c:
        yield c


@pytest.fixture
def lead_payload():
    with open(ROOT_DIR / "examples" / "normalized-lead.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.anyio
async def test_process_persists_and_reports_engine(client, lead_payload):
    resp = await client.post("/api/leads/process", json=lead_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["id"], int)
    assert data["meta"]["engine"] == "rules"
    assert data["meta"]["fallback_reason"] == "No model is set up."

    listing = (await client.get("/api/leads")).json()
    assert listing["total"] == 1
    assert listing["items"][0]["contact_name"] == "Somchai Prasert"
    assert listing["items"][0]["priority"] == "high"


@pytest.mark.anyio
async def test_process_without_saving(client, lead_payload):
    data = (await client.post("/api/leads/process?save=false", json=lead_payload)).json()
    assert data["id"] is None
    assert (await client.get("/api/leads")).json()["total"] == 0


@pytest.mark.anyio
async def test_detail_patch_delete(client, lead_payload):
    lead_id = (await client.post("/api/leads/process", json=lead_payload)).json()["id"]

    detail = (await client.get(f"/api/leads/{lead_id}")).json()
    assert detail["lead"]["message"] == lead_payload["message"]
    assert detail["score"]["total_score"] == 90

    patched = await client.patch(f"/api/leads/{lead_id}", json={"status": "contacted", "notes": "Left voicemail"})
    assert patched.status_code == 200
    assert patched.json()["status"] == "contacted"

    bad = await client.patch(f"/api/leads/{lead_id}", json={"status": "vanished"})
    assert bad.status_code == 422

    assert (await client.delete(f"/api/leads/{lead_id}")).status_code == 204
    assert (await client.get(f"/api/leads/{lead_id}")).status_code == 404


@pytest.mark.anyio
async def test_rescore_uses_current_profile(client, lead_payload):
    lead_id = (await client.post("/api/leads/process", json=lead_payload)).json()["id"]

    profile = (await client.get("/api/settings/profile")).json()
    profile["priority_thresholds"] = {"high": 95, "medium": 60, "low": 20}
    assert (await client.put("/api/settings/profile", json=profile)).status_code == 200

    rescored = (await client.post(f"/api/leads/{lead_id}/rescore")).json()
    assert rescored["score"]["priority"] == "medium"
    assert (await client.get("/api/leads?priority=medium")).json()["total"] == 1


@pytest.mark.anyio
async def test_rescore_all(client, lead_payload):
    await client.post("/api/leads/process", json=lead_payload)
    await client.post("/api/leads/process", json=lead_payload)

    profile = (await client.get("/api/settings/profile")).json()
    profile["priority_thresholds"] = {"high": 95, "medium": 60, "low": 20}
    await client.put("/api/settings/profile", json=profile)

    assert (await client.post("/api/leads/rescore-all")).json() == {"rescored": 2}
    assert (await client.get("/api/leads?priority=medium")).json()["total"] == 2


@pytest.mark.anyio
async def test_model_failure_falls_back_visibly(client, lead_payload):
    assert (await client.put("/api/settings/model", json=UNREACHABLE_MODEL)).status_code == 200

    data = (await client.post("/api/leads/process", json=lead_payload)).json()
    assert data["meta"]["engine"] == "rules"
    assert "reach" in data["meta"]["fallback_reason"]


@pytest.mark.anyio
async def test_model_failure_returns_502_when_fallback_disabled(client, lead_payload):
    await client.put("/api/settings/model", json={**UNREACHABLE_MODEL, "on_failure": "error"})

    resp = await client.post("/api/leads/process", json=lead_payload)
    assert resp.status_code == 502
    assert "reach" in resp.json()["detail"]
    assert (await client.get("/api/leads")).json()["total"] == 0


@pytest.mark.anyio
async def test_reanalyze_records_new_meta(client, lead_payload):
    lead_id = (await client.post("/api/leads/process", json=lead_payload)).json()["id"]
    await client.put("/api/settings/model", json=UNREACHABLE_MODEL)

    data = (await client.post(f"/api/leads/{lead_id}/reanalyze")).json()
    assert "reach" in data["meta"]["fallback_reason"]


@pytest.mark.anyio
async def test_empty_message_is_rejected(client):
    resp = await client.post("/api/leads/process", json={"contact": {"name": "A"}, "message": "   "})
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_oversized_message_is_rejected(client):
    resp = await client.post("/api/leads/process", json={"contact": {"name": "A"}, "message": "x" * 20001})
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_csv_export(client, lead_payload):
    await client.post("/api/leads/process", json=lead_payload)
    resp = await client.get("/api/leads/export.csv")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "Somchai Prasert" in resp.text


@pytest.mark.anyio
async def test_unknown_lead_is_404(client):
    assert (await client.get("/api/leads/424242")).status_code == 404
    assert (await client.post("/api/leads/424242/rescore")).status_code == 404
