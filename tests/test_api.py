"""
test_api.py
Integration tests for the AI Lead Automation FastAPI MVP server.
Tests /health, /api/samples, /api/leads/process, and /api/leads/normalize.
"""

import json
from pathlib import Path
import pytest
import httpx

from scripts.serve_api import app

ROOT_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
async def client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://127.0.0.1"
    ) as c:
        yield c


@pytest.mark.anyio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.anyio
async def test_get_samples(client):
    response = await client.get("/api/samples")
    assert response.status_code == 200
    samples = response.json()
    assert isinstance(samples, list)
    assert len(samples) >= 10
    assert any(s["lead_id"] == "lead_eval_001" for s in samples)


@pytest.mark.anyio
async def test_process_lead_canonical(client):
    with open(ROOT_DIR / "examples" / "normalized-lead.json", "r", encoding="utf-8") as f:
        payload = json.load(f)

    response = await client.post("/api/leads/process", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "lead" in data
    assert "analysis" in data
    assert "score" in data
    assert "dispatch" in data

    score = data["score"]
    assert score["total_score"] >= 80
    assert score["priority"] == "high"
    assert "hubspot" in data["dispatch"]
    assert "slack" in data["dispatch"]


@pytest.mark.anyio
async def test_process_lead_raw_website(client):
    with open(ROOT_DIR / "examples" / "incoming-lead.json", "r", encoding="utf-8") as f:
        payload = json.load(f)

    response = await client.post("/api/leads/process", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["lead"]["source"] == "website"
    assert data["lead"]["contact"]["name"] == "Somchai Prasert"
    assert data["score"]["priority"] == "high"


@pytest.mark.anyio
async def test_process_spam_lead_flagging(client):
    with open(ROOT_DIR / "evaluation" / "datasets" / "sample-leads.json", "r", encoding="utf-8") as f:
        samples = json.load(f)
    spam_lead = next(s for s in samples if s["lead_id"] == "lead_eval_007")

    response = await client.post("/api/leads/process", json=spam_lead)
    assert response.status_code == 200
    data = response.json()
    assert data["score"]["priority"] == "disqualified"
    assert data["score"]["total_score"] == 0
    assert data["score"]["requires_human_review"] is True


@pytest.mark.anyio
async def test_normalize_endpoint(client):
    with open(ROOT_DIR / "examples" / "incoming-lead.json", "r", encoding="utf-8") as f:
        payload = json.load(f)

    response = await client.post("/api/leads/normalize", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "website"
    assert "lead_id" in data
    assert data["contact"]["email"] == "somchai.p@bangkokbites.co.th"


@pytest.mark.anyio
async def test_serve_web_app(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert "AI Lead Automation" in response.text
    assert "Analyze lead" in response.text

    script = await client.get("/js/app.js")
    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]

