"""
test_ai_extractor.py
Orchestration between the configured model and the rules engine:
failures are never silent, and the chosen engine is reported in `meta`.
"""

import json

import pytest

from scripts.ai_extractor import ModelUnavailableError, analyze_lead, build_request, run_analysis
from scripts.business_profile import load_default_profile
from scripts.llm.providers import ProviderError
from scripts.llm.settings_store import ModelSettings
from scripts.paths import ROOT_DIR

CONFIGURED = ModelSettings(provider="openai", base_url="https://api.openai.com/v1", model="gpt-test", api_key="sk-x")


@pytest.fixture
def lead():
    with open(ROOT_DIR / "examples" / "normalized-lead.json", encoding="utf-8") as f:
        return json.load(f)


def model_output(**overrides):
    base = {
        "industry": "restaurant",
        "service_requested": "LINE bot",
        "service_match": {"offering": "line ai customer service", "tier": "adjacent"},
        "problem": "Staff overwhelmed by repetitive chats.",
        "contact_role": None,
        "budget": {"amount": 80000, "currency": "THB", "stated": True},
        "timeline_days": 28,
        "intent": "high",
        "language": "en",
        "summary": "Restaurant group wants a LINE bot.",
        "missing_information": [],
        "confidence_score": 0.9,
    }
    base.update(overrides)
    return base


class FakeProvider:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.requests = result, error, []

    def extract(self, request):
        self.requests.append(request)
        if self.error:
            raise self.error
        return self.result


def test_without_model_uses_rules_and_says_why(lead):
    analysis, meta = run_analysis(lead, load_default_profile(), ModelSettings())
    assert meta["engine"] == "rules"
    assert meta["fallback_reason"] == "No model is set up."
    assert analysis["intent"] == "high"


def test_model_result_is_used_and_catalog_tier_is_authoritative(lead):
    provider = FakeProvider(result=model_output())
    analysis, meta = run_analysis(lead, load_default_profile(), CONFIGURED, provider=provider)

    assert meta["engine"] == "model"
    assert meta["model"] == "gpt-test"
    assert meta["fallback_reason"] is None
    # Offering name is normalized to the catalog entry and its tier wins over the model's guess.
    assert analysis["service_match"] == {"offering": "LINE AI customer service", "tier": "core"}


def test_model_failure_falls_back_with_reason(lead):
    provider = FakeProvider(error=ProviderError("The model timed out after 5s."))
    analysis, meta = run_analysis(lead, load_default_profile(), CONFIGURED, provider=provider)

    assert meta["engine"] == "rules"
    assert meta["fallback_reason"] == "The model timed out after 5s."
    assert analysis["intent"] == "high"


def test_model_failure_raises_when_fallback_disabled(lead):
    settings = CONFIGURED.model_copy(update={"on_failure": "error"})
    provider = FakeProvider(error=ProviderError("The provider rejected the API key (401)."))

    with pytest.raises(ModelUnavailableError, match="401"):
        run_analysis(lead, load_default_profile(), settings, provider=provider)


def test_prompt_contains_catalog_and_treats_message_as_data(lead):
    request = build_request(lead, load_default_profile(), CONFIGURED.model_copy(update={"extra_instructions": "Prefer Thai summaries."}))

    assert "LINE AI customer service" in request.system
    assert "core" in request.system
    assert "untrusted" in request.system.lower()
    assert "Prefer Thai summaries." in request.system
    assert lead["message"] in request.user
    assert request.schema["properties"]["service_match"]


def test_analyze_lead_default_is_deterministic_rules(lead):
    assert analyze_lead(lead)["intent"] == "high"
