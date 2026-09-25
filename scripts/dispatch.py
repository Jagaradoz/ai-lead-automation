"""
dispatch.py
Downstream dispatch payloads (HubSpot contact, Slack alert) and optional live sync.
"""

import os
from typing import Any, Dict

import httpx

HUBSPOT_CONTACTS_URL = "https://api.hubapi.com/crm/v3/objects/contacts"
DISPATCH_TIMEOUT_S = 5
_HUBSPOT_PLACEHOLDER = "your_hubspot_private_app_token_here"


def build_hubspot_payload(lead: Dict[str, Any], analysis: Dict[str, Any], score: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "endpoint": HUBSPOT_CONTACTS_URL,
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


def _mrkdwn(text: Any) -> str:
    """Escapes lead-supplied text so it can't inject Slack mentions or links."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_slack_alert(lead: Dict[str, Any], analysis: Dict[str, Any], score: Dict[str, Any]) -> Dict[str, Any]:
    company_name = _mrkdwn(lead.get("company", {}).get("name") or "No company provided")
    prospect_name = _mrkdwn(lead.get("contact", {}).get("name") or "Unknown prospect")
    total_score = score.get("total_score", 0)
    service_req = _mrkdwn(analysis.get("service_requested") or "Not specified")
    summary_text = _mrkdwn(analysis.get("summary") or "Lead processed through automation pipeline.")

    return {
        "channel": "#sales-leads-alert",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"New lead: score {total_score}/100"},
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


def run_live_sync(hubspot_payload: Dict[str, Any], slack_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Sends the payloads when HUBSPOT_ACCESS_TOKEN / SLACK_WEBHOOK_URL are configured."""
    results: Dict[str, Any] = {}
    hubspot_token = os.environ.get("HUBSPOT_ACCESS_TOKEN")
    if hubspot_token and hubspot_token != _HUBSPOT_PLACEHOLDER:
        try:
            resp = httpx.post(
                hubspot_payload["endpoint"],
                json={"properties": hubspot_payload["properties"]},
                headers={"Authorization": f"Bearer {hubspot_token}"},
                timeout=DISPATCH_TIMEOUT_S,
            )
            results["hubspot"] = {"status_code": resp.status_code}
        except httpx.HTTPError as err:
            results["hubspot"] = {"error": type(err).__name__}

    slack_url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if slack_url.startswith("https://hooks.slack.com/") and "xxx/yyy" not in slack_url:
        try:
            resp = httpx.post(slack_url, json=slack_payload, timeout=DISPATCH_TIMEOUT_S)
            results["slack"] = {"status_code": resp.status_code}
        except httpx.HTTPError as err:
            results["slack"] = {"error": type(err).__name__}
    return results
