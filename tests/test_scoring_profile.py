"""
test_scoring_profile.py
The deterministic scoring engine must take every number and list from the business profile.
"""

import json

import pytest
from jsonschema import validate

from scripts.business_profile import BusinessProfile, load_default_profile
from scripts.paths import ROOT_DIR
from scripts.scoring_engine import score_lead


@pytest.fixture
def lead():
    with open(ROOT_DIR / "examples" / "normalized-lead.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def analysis():
    with open(ROOT_DIR / "examples" / "ai-analysis.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def score_schema():
    with open(ROOT_DIR / "schemas" / "lead-score.schema.json", encoding="utf-8") as f:
        return json.load(f)


def edited(mutator) -> BusinessProfile:
    data = load_default_profile().model_dump()
    mutator(data)
    return BusinessProfile(**data)


def by_dimension(result):
    return {e["dimension"]: e for e in result["explanations"]}


def test_default_profile_reproduces_reference_score(lead, analysis, score_schema):
    result = score_lead(lead, analysis)
    validate(instance=result, schema=score_schema)
    assert result["total_score"] == 90
    assert result["priority"] == "high"


def test_service_match_tier_drives_service_fit(lead, analysis):
    adjacent = {**analysis, "service_match": {"offering": "E-commerce and API integration", "tier": "adjacent"}}
    assert score_lead(lead, adjacent)["score_breakdown"]["service_fit"] == 15

    out = {**analysis, "service_match": {"offering": "SEO and backlinks", "tier": "out_of_scope"}}
    result = score_lead(lead, out)
    assert result["score_breakdown"]["service_fit"] == 0
    assert any("unsupported" in r.lower() for r in result["human_review_reasons"])


def test_moving_a_service_to_another_tier_changes_keyword_fallback(lead, analysis):
    def demote_line(data):
        for svc in data["services"]:
            if svc["name"] == "LINE AI customer service":
                svc["tier"] = "adjacent"
        for svc in data["services"]:
            if svc["name"] == "AI chatbot for customer questions":
                svc["keywords"] = ["chatbot"]

    without_match = {k: v for k, v in analysis.items() if k != "service_match"}
    result = score_lead(lead, without_match, profile=edited(demote_line))
    assert result["score_breakdown"]["service_fit"] == 15


def test_weights_change_max_points_and_total(lead, analysis):
    def reweight(data):
        data["scoring"]["weights"] = {
            "service_fit": 40, "purchase_intent": 20, "urgency": 10, "budget_fit": 10,
            "decision_authority": 10, "company_fit": 5, "data_completeness": 5,
        }

    result = score_lead(lead, analysis, profile=edited(reweight))
    dims = by_dimension(result)
    assert dims["service_fit"]["max_possible"] == 40
    assert dims["service_fit"]["points_awarded"] == 40
    assert dims["budget_fit"]["points_awarded"] == 8  # 75% of 10 (80k THB tier)
    assert sum(e["max_possible"] for e in result["explanations"]) == 100


def test_budget_tiers_are_configurable(lead, analysis):
    def raise_bar(data):
        data["scoring"]["budget_fit"]["tiers"] = [
            {"min_amount": 1_000_000, "share": 100},
            {"min_amount": 0, "share": 25},
        ]

    assert score_lead(lead, analysis, profile=edited(raise_bar))["score_breakdown"]["budget_fit"] == 5


def test_foreign_currency_uses_profile_rates(lead, analysis):
    usd = {**analysis, "budget": {"amount": 3000, "currency": "USD", "stated": True}}
    assert score_lead(lead, usd)["score_breakdown"]["budget_fit"] == 20  # 105,000 THB

    def cheap_dollar(data):
        data["currency_rates"]["USD"] = 10

    assert score_lead(lead, usd, profile=edited(cheap_dollar))["score_breakdown"]["budget_fit"] == 5


def test_contact_role_grants_decision_authority(lead, analysis):
    with_role = {**analysis, "contact_role": "Managing Director"}
    assert score_lead(lead, with_role)["score_breakdown"]["decision_authority"] == 5


def test_thresholds_are_configurable(lead, analysis):
    def strict(data):
        data["priority_thresholds"] = {"high": 95, "medium": 60, "low": 20}

    assert score_lead(lead, analysis, profile=edited(strict))["priority"] == "medium"


def test_large_budget_review_threshold_is_configurable(lead, analysis):
    def small_large(data):
        data["review"]["large_budget_at_least"] = 50_000

    result = score_lead(lead, analysis, profile=edited(small_large))
    assert any("large opportunity" in r.lower() for r in result["human_review_reasons"])


def test_spam_zeroes_score(lead, analysis):
    spam = {**analysis, "intent": "spam"}
    result = score_lead(lead, spam)
    assert result["total_score"] == 0
    assert result["priority"] == "disqualified"
