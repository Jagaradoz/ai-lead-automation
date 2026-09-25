#!/usr/bin/env python3
"""
normalize.py
Channel Adapters & Canonical Lead Normalization Engine.
Transforms heterogeneous incoming payloads (Website forms, Facebook Lead Ads, LINE OA)
into the unified Canonical Lead model matching schemas/lead.schema.json.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from jsonschema import validate

ROOT_DIR = Path(__file__).resolve().parent.parent
LEAD_SCHEMA_PATH = ROOT_DIR / "schemas" / "lead.schema.json"


def load_lead_schema() -> Dict[str, Any]:
    with open(LEAD_SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_lead_id() -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    short_uuid = uuid.uuid4().hex[:8]
    return f"lead_{today}_{short_uuid}"


def normalize_website_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforms website form submissions (e.g., examples/incoming-lead.json)
    into a Canonical Lead.
    """
    fields = payload.get("fields", {})
    tracking = payload.get("tracking", {})
    timestamp = payload.get("timestamp")

    if timestamp:
        try:
            received_at = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        except Exception:
            received_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    else:
        received_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    canonical_lead = {
        "lead_id": generate_lead_id(),
        "source": "website",
        "external_id": payload.get("submission_id"),
        "contact": {
            "name": fields.get("full_name") or fields.get("name") or "Website Inquirer",
            "email": fields.get("work_email") or fields.get("email"),
            "phone": fields.get("contact_number") or fields.get("phone"),
        },
        "company": {
            "name": fields.get("company_title") or fields.get("company_name") or fields.get("company"),
            "website": fields.get("website") or fields.get("company_website"),
            "size": fields.get("company_size") or fields.get("size"),
        },
        "message": fields.get("inquiry_text") or fields.get("message") or "",
        "received_at": received_at,
        "metadata": {
            "utm_source": tracking.get("source"),
            "utm_medium": tracking.get("medium"),
            "utm_campaign": tracking.get("campaign"),
            "landing_page": tracking.get("landing_url") or tracking.get("landing_page"),
            "ip_address": payload.get("client_ip"),
        },
    }

    return canonical_lead


def normalize_line_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforms LINE Official Account webhook events into a Canonical Lead.
    """
    events = payload.get("events", [{}])
    event = events[0] if events else {}
    source = event.get("source", {})
    msg = event.get("message", {})

    canonical_lead = {
        "lead_id": generate_lead_id(),
        "source": "line",
        "external_id": source.get("userId"),
        "contact": {
            "name": payload.get("profile", {}).get("displayName") or "LINE User",
            "email": payload.get("email"),
            "phone": payload.get("phone"),
        },
        "company": {
            "name": payload.get("company_name"),
            "website": None,
            "size": None,
        },
        "message": msg.get("text") or "",
        "received_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "metadata": {
            "line_reply_token": event.get("replyToken"),
            "channel_type": source.get("type", "user"),
        },
    }

    return canonical_lead


def normalize_facebook_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforms Meta / Facebook Leadgen webhook retrieval payloads into a Canonical Lead.
    """
    leadgen_id = payload.get("leadgen_id") or payload.get("id")
    field_data = payload.get("field_data", [])

    extracted_fields = {}
    for item in field_data:
        name = item.get("name")
        values = item.get("values", [])
        if name and values:
            extracted_fields[name] = values[0]

    canonical_lead = {
        "lead_id": generate_lead_id(),
        "source": "facebook",
        "external_id": str(leadgen_id) if leadgen_id else None,
        "contact": {
            "name": extracted_fields.get("full_name") or extracted_fields.get("name") or "Facebook Lead",
            "email": extracted_fields.get("email"),
            "phone": extracted_fields.get("phone_number") or extracted_fields.get("phone"),
        },
        "company": {
            "name": extracted_fields.get("company_name"),
            "website": None,
            "size": None,
        },
        "message": extracted_fields.get("notes") or extracted_fields.get("custom_question") or "",
        "received_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "metadata": {
            "form_id": payload.get("form_id"),
            "ad_id": payload.get("ad_id"),
            "campaign_id": payload.get("campaign_id"),
        },
    }

    return canonical_lead


def normalize_lead(payload: Dict[str, Any], source: Optional[str] = None, validate_schema: bool = True) -> Dict[str, Any]:
    """
    Main normalization entry point. Automatically detects or enforces source adapter,
    transforms to Canonical Lead, and validates against JSON Schema.
    """
    detected_source = source

    if not detected_source:
        if "form_name" in payload or "submission_id" in payload:
            detected_source = "website"
        elif "events" in payload:
            detected_source = "line"
        elif "field_data" in payload or "leadgen_id" in payload:
            detected_source = "facebook"
        elif "lead_id" in payload and "contact" in payload:
            # Already canonical
            if validate_schema:
                validate(instance=payload, schema=load_lead_schema())
            return payload
        else:
            detected_source = "website"

    if detected_source == "website":
        normalized = normalize_website_payload(payload)
    elif detected_source == "line":
        normalized = normalize_line_payload(payload)
    elif detected_source == "facebook":
        normalized = normalize_facebook_payload(payload)
    else:
        normalized = normalize_website_payload(payload)

    if validate_schema:
        validate(instance=normalized, schema=load_lead_schema())

    return normalized


if __name__ == "__main__":
    test_incoming = ROOT_DIR / "examples" / "incoming-lead.json"
    with open(test_incoming, "r", encoding="utf-8") as f:
        incoming_data = json.load(f)

    result = normalize_lead(incoming_data)
    print("Successfully normalized incoming website payload to Canonical Lead:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
