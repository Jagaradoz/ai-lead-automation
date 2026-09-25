"""
business_profile.py
The editable description of *your* business: what you sell, who you sell to,
and how leads are scored. Both the AI prompt and the deterministic scoring
engine read from this profile, so nothing about the business is hardcoded.

The shipped default lives in config/business-profile.default.json.
Edits from the Settings page are saved to <DATA_DIR>/business-profile.json.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from scripts.paths import CONFIG_DIR, data_dir

DEFAULT_PROFILE_PATH = CONFIG_DIR / "business-profile.default.json"

Share = Field(ge=0, le=100)
_Frozen = ConfigDict(frozen=True)


class Business(BaseModel):
    model_config = _Frozen
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(max_length=2000)
    base_currency: str = Field(min_length=3, max_length=3)

    @field_validator("base_currency")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class Service(BaseModel):
    model_config = _Frozen
    name: str = Field(min_length=1, max_length=120)
    tier: Literal["core", "adjacent", "out_of_scope"]
    keywords: List[str] = Field(default_factory=list, max_length=50)

    @field_validator("keywords")
    @classmethod
    def _clean(cls, v: List[str]) -> List[str]:
        return [k.strip().lower() for k in v if k.strip()]


class Industry(BaseModel):
    model_config = _Frozen
    name: str = Field(min_length=1, max_length=60)
    target: bool = False
    keywords: List[str] = Field(default_factory=list, max_length=50)

    @field_validator("keywords")
    @classmethod
    def _clean(cls, v: List[str]) -> List[str]:
        return [k.strip().lower() for k in v if k.strip()]


class Weights(BaseModel):
    model_config = _Frozen
    service_fit: int = Share
    purchase_intent: int = Share
    urgency: int = Share
    budget_fit: int = Share
    decision_authority: int = Share
    company_fit: int = Share
    data_completeness: int = Share

    @model_validator(mode="after")
    def _sum_to_100(self):
        total = sum(self.model_dump().values())
        if total != 100:
            raise ValueError(f"Dimension weights must add up to 100 (currently {total}).")
        return self


class ServiceFitShares(BaseModel):
    model_config = _Frozen
    core: int = Share
    adjacent: int = Share
    uncatalogued: int = Share
    out_of_scope: int = Share


class IntentShares(BaseModel):
    model_config = _Frozen
    high: int = Share
    medium: int = Share
    low: int = Share


class UrgencyBucket(BaseModel):
    model_config = _Frozen
    max_days: int = Field(ge=0, le=3650)
    share: int = Share


class Urgency(BaseModel):
    model_config = _Frozen
    buckets: List[UrgencyBucket] = Field(min_length=1, max_length=10)
    beyond: int = Share
    unspecified: int = Share

    @field_validator("buckets")
    @classmethod
    def _sorted(cls, v: List[UrgencyBucket]) -> List[UrgencyBucket]:
        return sorted(v, key=lambda b: b.max_days)


class BudgetTier(BaseModel):
    model_config = _Frozen
    min_amount: float = Field(ge=0)
    share: int = Share


class BudgetFit(BaseModel):
    model_config = _Frozen
    tiers: List[BudgetTier] = Field(min_length=1, max_length=10)
    unspecified: int = Share

    @field_validator("tiers")
    @classmethod
    def _sorted(cls, v: List[BudgetTier]) -> List[BudgetTier]:
        return sorted(v, key=lambda t: t.min_amount, reverse=True)


class Completeness(BaseModel):
    model_config = _Frozen
    full: int = Share
    basic: int = Share


class Scoring(BaseModel):
    model_config = _Frozen
    weights: Weights
    service_fit: ServiceFitShares
    purchase_intent: IntentShares
    urgency: Urgency
    budget_fit: BudgetFit
    data_completeness: Completeness


class Thresholds(BaseModel):
    model_config = _Frozen
    high: int = Field(ge=0, le=100)
    medium: int = Field(ge=0, le=100)
    low: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def _descending(self):
        if not (self.high > self.medium > self.low):
            raise ValueError("Priority thresholds must satisfy high > medium > low.")
        return self


class Review(BaseModel):
    model_config = _Frozen
    low_confidence_below: float = Field(ge=0, le=1)
    large_budget_at_least: float = Field(ge=0)
    flag_out_of_scope: bool = True
    flag_spam: bool = True
    flag_ambiguous: bool = True


class BusinessProfile(BaseModel):
    model_config = _Frozen
    version: int = 1
    business: Business
    currency_rates: Dict[str, float]
    services: List[Service] = Field(max_length=100)
    industries: List[Industry] = Field(max_length=100)
    target_company_sizes: List[str] = Field(default_factory=list, max_length=20)
    decision_maker_titles: List[str] = Field(default_factory=list, max_length=100)
    spam_phrases: List[str] = Field(default_factory=list, max_length=200)
    scoring: Scoring
    priority_thresholds: Thresholds
    review: Review

    @field_validator("currency_rates")
    @classmethod
    def _rates(cls, v: Dict[str, float]) -> Dict[str, float]:
        cleaned = {code.upper(): float(rate) for code, rate in v.items()}
        if any(rate <= 0 for rate in cleaned.values()):
            raise ValueError("Currency rates must be positive.")
        return cleaned

    @field_validator("decision_maker_titles", "spam_phrases")
    @classmethod
    def _lower(cls, v: List[str]) -> List[str]:
        return [item.strip().lower() for item in v if item.strip()]

    @model_validator(mode="after")
    def _consistency(self):
        base = self.business.base_currency
        if base not in self.currency_rates:
            raise ValueError(f"Add a currency rate for the base currency {base}.")
        names = [s.name.lower() for s in self.services]
        if len(names) != len(set(names)):
            raise ValueError("Service names must be unique.")
        return self

    def to_base_currency(self, amount: Optional[float], currency: Optional[str]) -> Optional[float]:
        """Converts an amount into the base currency. Unknown currencies are treated as base."""
        if amount is None:
            return None
        code = (currency or self.business.base_currency).upper()
        rate = self.currency_rates.get(code)
        base_rate = self.currency_rates[self.business.base_currency]
        if rate is None:
            return float(amount)
        return float(amount) * rate / base_rate


def _read(path: Path) -> BusinessProfile:
    with open(path, "r", encoding="utf-8") as f:
        return BusinessProfile(**json.load(f))


def load_default_profile() -> BusinessProfile:
    return _read(DEFAULT_PROFILE_PATH)


class ProfileStore:
    def __init__(self, path: Optional[Path] = None):
        self._path = path or data_dir() / "business-profile.json"

    def load(self) -> BusinessProfile:
        return _read(self._path) if self._path.exists() else load_default_profile()

    def save(self, profile: BusinessProfile) -> BusinessProfile:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(profile.model_dump(), f, indent=2, ensure_ascii=False)
        os.replace(tmp, self._path)
        return profile

    def reset(self) -> BusinessProfile:
        if self._path.exists():
            self._path.unlink()
        return load_default_profile()
