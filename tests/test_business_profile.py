"""
test_business_profile.py
Validation and persistence tests for the editable business profile.
"""

import pytest
from pydantic import ValidationError

from scripts.business_profile import BusinessProfile, ProfileStore, load_default_profile


def default_dict():
    return load_default_profile().model_dump()


def test_default_profile_is_valid_and_weights_sum_to_100():
    profile = load_default_profile()
    assert sum(profile.scoring.weights.model_dump().values()) == 100
    assert any(s.tier == "core" for s in profile.services)


def test_weights_must_sum_to_100():
    data = default_dict()
    data["scoring"]["weights"]["service_fit"] = 40
    with pytest.raises(ValidationError, match="100"):
        BusinessProfile(**data)


def test_thresholds_must_descend():
    data = default_dict()
    data["priority_thresholds"] = {"high": 40, "medium": 45, "low": 20}
    with pytest.raises(ValidationError):
        BusinessProfile(**data)


def test_budget_tiers_are_sorted_descending_on_load():
    data = default_dict()
    data["scoring"]["budget_fit"]["tiers"] = [
        {"min_amount": 0, "share": 25},
        {"min_amount": 100000, "share": 100},
    ]
    profile = BusinessProfile(**data)
    assert [t.min_amount for t in profile.scoring.budget_fit.tiers] == [100000, 0]


def test_base_currency_needs_a_rate():
    data = default_dict()
    data["business"]["base_currency"] = "JPY"
    with pytest.raises(ValidationError, match="JPY"):
        BusinessProfile(**data)


def test_service_names_must_be_unique():
    data = default_dict()
    data["services"].append(dict(data["services"][0]))
    with pytest.raises(ValidationError, match="unique"):
        BusinessProfile(**data)


def test_store_falls_back_to_default_then_persists(tmp_path):
    store = ProfileStore(tmp_path / "profile.json")
    assert store.load() == load_default_profile()

    data = default_dict()
    data["business"]["name"] = "Acme Bots"
    saved = store.save(BusinessProfile(**data))
    assert store.load().business.name == "Acme Bots" == saved.business.name

    assert store.reset() == load_default_profile()
    assert store.load() == load_default_profile()
