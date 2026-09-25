#!/usr/bin/env python3
"""
serve_api.py
FastAPI MVP Server & Local Runner for AI Lead Automation.
Provides standalone REST API endpoints for lead ingestion, normalization,
AI fact extraction, deterministic scoring, and downstream dispatch preview.
Serves the interactive demo web application directly on GET /.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Load .env if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


from scripts.normalize import normalize_lead
from scripts.ai_extractor import analyze_lead
from scripts.scoring_engine import score_lead

DATASET_PATH = ROOT_DIR / "evaluation" / "datasets" / "sample-leads.json"
DEMO_HTML_PATH = ROOT_DIR / "examples" / "demo" / "index.html"

app = FastAPI(
    title="AI Lead Automation MVP Engine",
    description="Channel-independent lead intake, AI fact extraction, and deterministic scoring API.",
    version="1.0.0",
)

# Enable CORS for frontend integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def build_hubspot_payload(lead: Dict[str, Any], analysis: Dict[str, Any], score: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "endpoint": "https://api.hubapi.com/crm/v3/objects/contacts",
        "method": "POST",
        "properties": {
            "email": lead.get("contact", {}).get("email"),
            "firstname": lead.get("contact", {}).get("name"),
            "phone": lead.get("contact", {}).get("phone"),
            "company": lead.get("company", {}).get("name"),
            "lead_score_total": score.get("total_score", 0),
            "lead_score_priority": score.get("priority", "low"),
            "ai_lead_summary": analysis.get("summary", ""),
            "requires_human_review": str(score.get("requires_human_review", False)).lower(),
        },
    }


def build_slack_alert(lead: Dict[str, Any], analysis: Dict[str, Any], score: Dict[str, Any]) -> Dict[str, Any]:
    company_name = lead.get("company", {}).get("name") or "No company provided"
    prospect_name = lead.get("contact", {}).get("name") or "Unknown Prospect"
    total_score = score.get("total_score", 0)
    service_req = analysis.get("service_requested") or "Not specified"
    summary_text = analysis.get("summary") or "Lead processed through automation pipeline."

    return {
        "channel": "#sales-leads-alert",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🔥 High Priority Lead Alert (Score: {total_score}/100)",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Prospect:* {prospect_name} ({company_name})\n"
                        f"*Service:* {service_req}\n"
                        f"*Score:* {total_score} | Priority: *{score.get('priority', '').upper()}*\n"
                        f"*Summary:* {summary_text}"
                    ),
                },
            },
        ],
    }


@app.get("/health")
def health():
    openai_key_present = bool(os.environ.get("OPENAI_API_KEY") and os.environ.get("OPENAI_API_KEY") != "your_openai_api_key_here")
    return {
        "status": "ok",
        "version": "1.0.0",
        "ai_engine_mode": "live_openai" if openai_key_present else "offline_heuristic_fallback",
        "system": "AI Lead Automation MVP Engine",
    }


@app.get("/api/samples")
def get_samples():
    """Returns the benchmark sample leads for 1-click testing in the UI."""
    if not DATASET_PATH.exists():
        raise HTTPException(status_code=404, detail="Sample dataset not found.")
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/leads/normalize")
async def normalize_endpoint(request: Request):
    """Takes any raw or partial lead payload and normalizes it into a Canonical Lead."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    try:
        canonical = normalize_lead(body)
        return canonical
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Normalization failed: {str(e)}")


@app.post("/api/leads/process")
async def process_lead_endpoint(request: Request, live_sync: bool = Query(False)):
    """
    Executes the entire end-to-end Lead Intelligence pipeline:
    1. Normalization (raw channel -> canonical lead)
    2. AI Fact Extraction (OpenAI structured output or offline heuristics)
    3. Deterministic Scoring Engine (0-100 pts, breakdown, priority, review flags)
    4. Downstream Dispatch Preparation (HubSpot CRM & Slack alert payloads)
    """
    start_time = time.time()
    try:
        raw_body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    try:
        # Step 1: Normalize
        canonical_lead = normalize_lead(raw_body)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Schema or Normalization Error: {str(e)}")

    try:
        # Step 2: AI Fact Extraction
        analysis = analyze_lead(canonical_lead)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Extraction Error: {str(e)}")

    try:
        # Step 3: Deterministic Rule Scoring
        score_res = score_lead(canonical_lead, analysis)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scoring Engine Error: {str(e)}")

    # Step 4: Downstream Dispatch Artifacts
    hubspot_payload = build_hubspot_payload(canonical_lead, analysis, score_res)
    slack_payload = build_slack_alert(canonical_lead, analysis, score_res)

    live_results = {}
    if live_sync:
        # Optional live HubSpot sync if token is set
        hubspot_token = os.environ.get("HUBSPOT_ACCESS_TOKEN")
        if hubspot_token and hubspot_token != "your_hubspot_private_app_token_here":
            try:
                import requests
                hs_resp = requests.post(
                    hubspot_payload["endpoint"],
                    json={"properties": hubspot_payload["properties"]},
                    headers={"Authorization": f"Bearer {hubspot_token}", "Content-Type": "application/json"},
                    timeout=5,
                )
                live_results["hubspot"] = {"status_code": hs_resp.status_code, "response": hs_resp.text}
            except Exception as hs_err:
                live_results["hubspot"] = {"error": str(hs_err)}

        # Optional live Slack alert if webhook is set
        slack_url = os.environ.get("SLACK_WEBHOOK_URL")
        if slack_url and "hooks.slack.com" in slack_url:
            try:
                import requests
                sl_resp = requests.post(
                    slack_url,
                    json=slack_payload,
                    headers={"Content-Type": "application/json"},
                    timeout=5,
                )
                live_results["slack"] = {"status_code": sl_resp.status_code}
            except Exception as sl_err:
                live_results["slack"] = {"error": str(sl_err)}

    elapsed_ms = round((time.time() - start_time) * 1000, 2)

    return {
        "status": "success",
        "execution_time_ms": elapsed_ms,
        "lead": canonical_lead,
        "analysis": analysis,
        "score": score_res,
        "dispatch": {
            "hubspot": hubspot_payload,
            "slack": slack_payload,
            "live_sync_executed": bool(live_results),
            "live_sync_results": live_results,
        },
    }


@app.get("/", response_class=HTMLResponse)
def serve_demo():
    """Serves the interactive demo application."""
    if DEMO_HTML_PATH.exists():
        with open(DEMO_HTML_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return """
    <!DOCTYPE html>
    <html>
      <head><title>AI Lead Automation MVP</title></head>
      <body style="font-family:sans-serif;padding:40px;background:#0f172a;color:#fff;">
        <h1>AI Lead Automation API Running</h1>
        <p>Endpoints available:</p>
        <ul>
          <li><a style="color:#38bdf8" href="/health">/health</a></li>
          <li><a style="color:#38bdf8" href="/api/samples">/api/samples</a></li>
          <li><code>POST /api/leads/process</code></li>
        </ul>
      </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"[*] Starting AI Lead Automation MVP API Server on http://localhost:{port}")
    uvicorn.run("scripts.serve_api:app", host="0.0.0.0", port=port, reload=True)
