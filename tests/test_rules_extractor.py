"""
test_rules_extractor.py
The rules engine (used when no model is configured, or as a fallback) must read
real-world phrasing, not just the benchmark samples.
"""

import json

import pytest
from jsonschema import validate

from scripts.business_profile import BusinessProfile, load_default_profile
from scripts.paths import ROOT_DIR
from scripts.rules_extractor import extract_with_rules, parse_budget, parse_timeline

RECEIVED = "2026-09-25T10:00:00Z"


def lead(message, **overrides):
    base = {
        "lead_id": "lead_test",
        "source": "website",
        "contact": {"name": "Pat Doe", "email": "pat@example.com", "phone": "+66-81-000-0000"},
        "company": {"name": "Example Co", "website": None, "size": None},
        "message": message,
        "received_at": RECEIVED,
    }
    base.update(overrides)
    return base


@pytest.fixture(scope="module")
def schema():
    with open(ROOT_DIR / "schemas" / "lead-analysis.schema.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Our budget is around 2.5k USD.", (2500.0, "USD")),
        ("งบประมาณ 5 แสนบาท", (500000.0, "THB")),
        ("We can spend ฿80,000 on this", (80000.0, "THB")),
        ("Budget: 1.2 million baht", (1200000.0, "THB")),
        ("about €12,000", (12000.0, "EUR")),
        ("$15,000 USD (approx 500,000 THB)", (500000.0, "THB")),
        ("budget 90000", (90000.0, "THB")),
        ("We have 3 branches and 20 staff", None),
        ("It costs $20 monthly", (20.0, "USD")),
    ],
)
def test_parse_budget(text, expected):
    assert parse_budget(text.lower(), "THB") == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("we need it live within 3 weeks", 21),
        ("ต้องการใช้งานภายใน 3 สัปดาห์", 21),
        ("need it by next month", 30),
        ("can you start in two months?", 60),
        ("within the next 10 days please", 10),
        ("vendor responses by October 15th", 20),
        ("deadline is 1 November", 37),
        ("can someone come today", 1),
        ("this is urgent", 7),
        ("no rush, whenever works", None),
        ("we are open 7 days a week", None),
        ("", None),
    ],
)
def test_parse_timeline(text, expected):
    assert parse_timeline(text.lower(), RECEIVED) == expected


def test_unseen_high_intent_lead(schema):
    result = extract_with_rules(
        lead(
            "Hi, I'm the operations manager at a 3-branch dental clinic. We want a chatbot that answers "
            "patient questions on our website. Budget is approved at 150k THB and we want to go live within 6 weeks.",
            company={"name": "BrightSmile Dental", "website": None, "size": "11-50"},
        ),
        load_default_profile(),
    )
    validate(instance=result, schema=schema)
    assert result["intent"] == "high"
    assert result["industry"] == "healthcare"
    assert result["budget"] == {"amount": 150000.0, "currency": "THB", "stated": True}
    assert result["timeline_days"] == 42
    assert result["service_match"] == {"offering": "AI chatbot for customer questions", "tier": "core"}
    assert result["contact_role"] == "manager"


def test_catalog_edits_change_service_match():
    data = load_default_profile().model_dump()
    data["services"].append({"name": "Voice agents", "tier": "core", "keywords": ["voice agent", "phone bot"]})
    profile = BusinessProfile(**data)

    result = extract_with_rules(lead("Looking for a voice agent to answer our phone line after hours."), profile)
    assert result["service_match"] == {"offering": "Voice agents", "tier": "core"}
    assert result["service_requested"] == "Voice agents"


def test_spam_phrases_come_from_profile():
    data = load_default_profile().model_dump()
    data["spam_phrases"] = ["forex signals"]
    profile = BusinessProfile(**data)

    assert extract_with_rules(lead("Join our FOREX SIGNALS group for 300% returns"), profile)["intent"] == "spam"
    assert extract_with_rules(lead("Buy high DA backlinks now, special offer"), profile)["intent"] != "spam"


def test_short_message_is_ambiguous():
    result = extract_with_rules(lead("hello, info please"), load_default_profile())
    assert result["intent"] == "ambiguous"


def test_thai_language_detected():
    result = extract_with_rules(lead("สนใจทำแชทบอทสำหรับร้านอาหารครับ งบประมาณ 60,000 บาท ต้องการภายใน 1 เดือน"), load_default_profile())
    assert result["language"] == "th"
    assert result["industry"] == "restaurant"
    assert result["timeline_days"] == 30
