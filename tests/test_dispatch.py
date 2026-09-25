"""
test_dispatch.py
Downstream payloads must not let lead text inject Slack mentions or links.
"""

from scripts.dispatch import build_hubspot_payload, build_slack_alert


def test_slack_alert_escapes_lead_text():
    lead = {"contact": {"name": "<!channel> <https://phish.example|Reset SSO>"}, "company": {"name": "A & B"}}
    analysis = {"summary": "<@U123> hi", "service_requested": None}
    text = build_slack_alert(lead, analysis, {"total_score": 50, "priority": "medium"})["blocks"][1]["text"]["text"]

    assert "<!channel>" not in text and "<https://" not in text and "<@U123>" not in text
    assert "&lt;!channel&gt;" in text
    assert "A &amp; B" in text


def test_hubspot_payload_maps_score():
    lead = {"contact": {"name": "Pat", "email": "p@example.com", "phone": None}, "company": {"name": "Co"}}
    payload = build_hubspot_payload(lead, {"summary": "s"}, {"total_score": 80, "priority": "high"})
    assert payload["properties"]["lead_score_total"] == 80
    assert payload["properties"]["email"] == "p@example.com"
