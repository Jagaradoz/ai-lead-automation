"""
test_pipeline.py
Automated Unit and Integration Tests for AI Lead Automation.
Tests Schema validation, Channel Normalizers, Deterministic Scoring, and Benchmark fixtures.
"""

import json
import pytest
from pathlib import Path
from jsonschema import Draft7Validator, validate

from scripts.normalize import normalize_lead
from scripts.scoring_engine import score_lead
from scripts.ai_extractor import analyze_lead

ROOT_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def schemas():
    def load(path):
        with open(ROOT_DIR / path, "r", encoding="utf-8") as f:
            return json.load(f)

    return {
        "lead": load("schemas/lead.schema.json"),
        "analysis": load("schemas/lead-analysis.schema.json"),
        "score": load("schemas/lead-score.schema.json"),
    }


@pytest.fixture(scope="session")
def sample_leads():
    with open(ROOT_DIR / "evaluation" / "datasets" / "sample-leads.json", "r", encoding="utf-8") as f:
        return json.load(f)


def test_json_schemas_draft7_validity(schemas):
    """Verifies that all three core schemas are valid Draft-07 JSON Schemas."""
    for name, schema_def in schemas.items():
        Draft7Validator.check_schema(schema_def)


def test_channel_normalizer_website_payload(schemas):
    """Tests normalizer on raw website form submission."""
    with open(ROOT_DIR / "examples" / "incoming-lead.json", "r", encoding="utf-8") as f:
        raw_payload = json.load(f)

    canonical = normalize_lead(raw_payload, source="website")
    assert canonical["source"] == "website"
    assert canonical["contact"]["name"] == "Somchai Prasert"
    assert canonical["contact"]["email"] == "somchai.p@bangkokbites.co.th"
    validate(instance=canonical, schema=schemas["lead"])


def test_deterministic_scoring_exact_match(schemas):
    """Verifies that reference lead and analysis produces exact expected score."""
    with open(ROOT_DIR / "examples" / "normalized-lead.json", "r", encoding="utf-8") as f:
        lead = json.load(f)
    with open(ROOT_DIR / "examples" / "ai-analysis.json", "r", encoding="utf-8") as f:
        analysis = json.load(f)

    score_res = score_lead(lead, analysis)
    validate(instance=score_res, schema=schemas["score"])

    assert score_res["total_score"] == 90
    assert score_res["priority"] == "high"
    assert score_res["score_breakdown"]["service_fit"] == 25
    assert score_res["score_breakdown"]["purchase_intent"] == 20
    assert score_res["score_breakdown"]["urgency"] == 20
    assert score_res["score_breakdown"]["budget_fit"] == 15
    assert score_res["requires_human_review"] is False


def test_spam_lead_penalization_and_review(sample_leads, schemas):
    """Verifies that spam lead (eval_007) is penalized to 0 points and flagged for review."""
    spam_lead = next(l for l in sample_leads if l["lead_id"] == "lead_eval_007")
    analysis = analyze_lead(spam_lead)
    score_res = score_lead(spam_lead, analysis)

    assert analysis["intent"] == "spam"
    assert score_res["total_score"] == 0
    assert score_res["priority"] == "disqualified"
    assert score_res["requires_human_review"] is True
    assert any("spam" in r.lower() for r in score_res["human_review_reasons"])
    validate(instance=score_res, schema=schemas["score"])


def test_enterprise_opportunity_flagging(sample_leads, schemas):
    """Verifies that large enterprise budget (eval_008) is flagged for senior rep review."""
    ent_lead = next(l for l in sample_leads if l["lead_id"] == "lead_eval_008")
    analysis = analyze_lead(ent_lead)
    score_res = score_lead(ent_lead, analysis)

    assert score_res["priority"] == "high"
    assert score_res["total_score"] >= 80
    assert score_res["requires_human_review"] is True
    assert any("large opportunity" in r.lower() for r in score_res["human_review_reasons"])
    validate(instance=score_res, schema=schemas["score"])


def test_hardware_out_of_scope_flagging(sample_leads, schemas):
    """Verifies that hardware repair request (eval_006) gets 0 service points and review flag."""
    hw_lead = next(l for l in sample_leads if l["lead_id"] == "lead_eval_006")
    analysis = analyze_lead(hw_lead)
    score_res = score_lead(hw_lead, analysis)

    assert score_res["score_breakdown"]["service_fit"] == 0
    assert score_res["requires_human_review"] is True
    validate(instance=score_res, schema=schemas["score"])


def test_all_10_sample_leads_schema_compliance(sample_leads, schemas):
    """Verifies that every sample lead scores cleanly and conforms to schemas."""
    for lead in sample_leads:
        analysis = analyze_lead(lead)
        validate(instance=analysis, schema=schemas["analysis"])

        score_res = score_lead(lead, analysis)
        validate(instance=score_res, schema=schemas["score"])

        assert 0 <= score_res["total_score"] <= 100
        assert score_res["priority"] in ["high", "medium", "low", "disqualified"]
