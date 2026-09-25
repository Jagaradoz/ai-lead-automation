#!/usr/bin/env python3
"""
scoring_engine.py
Deterministic Lead Scoring Engine for AI Lead Automation.

Computes explainable, rule-based dimensional scores from a Canonical Lead and a
LeadAnalysis. Every point value, keyword list, threshold and currency rate comes
from the business profile (scripts/business_profile.py); nothing about the
business is hardcoded here. Output conforms to schemas/lead-score.schema.json.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from scripts.business_profile import BusinessProfile, load_default_profile
from scripts.paths import ROOT_DIR
from scripts.text_match import count_terms, first_term

DIMENSIONS = [
    "service_fit",
    "purchase_intent",
    "urgency",
    "budget_fit",
    "decision_authority",
    "company_fit",
    "data_completeness",
]
MIN_PHONE_LENGTH = 7


def _points(weight: int, share: int) -> int:
    """Share (0-100 %) of a dimension's weight, rounded half-up."""
    return int(weight * share / 100 + 0.5)


def resolve_service_tier(analysis: Dict[str, Any], profile: BusinessProfile) -> Tuple[str, Optional[str]]:
    """
    Returns (tier, offering). Uses the AI's service_match when present, otherwise
    matches service_requested/problem against the catalog by name and keywords.
    Tier is one of core | adjacent | out_of_scope | uncatalogued | none.
    """
    service = (analysis.get("service_requested") or "").strip()
    match = analysis.get("service_match") or {}
    tier = match.get("tier")
    if tier in ("core", "adjacent", "out_of_scope"):
        return tier, match.get("offering")
    if tier == "none":
        return ("uncatalogued" if service else "none"), None

    by_name = {s.name.lower(): s for s in profile.services}
    if service.lower() in by_name:
        svc = by_name[service.lower()]
        return svc.tier, svc.name

    text = f"{service} {analysis.get('problem') or ''}".lower()
    tier_rank = {"core": 0, "adjacent": 1, "out_of_scope": 2}
    scored = [(count_terms(text, s.keywords), -tier_rank[s.tier], s) for s in profile.services]
    hits, _, best = max(scored, key=lambda item: (item[0], item[1]), default=(0, 0, None))
    if best is not None and hits > 0:
        return best.tier, best.name
    return ("uncatalogued" if service else "none"), None


def evaluate_service_fit(analysis: Dict[str, Any], profile: BusinessProfile, weight: int) -> Tuple[int, str, str]:
    intent = (analysis.get("intent") or "").lower()
    if intent in ("ambiguous", "spam"):
        return 0, "No identifiable service request in an ambiguous or spam submission.", "none"

    tier, offering = resolve_service_tier(analysis, profile)
    shares = profile.scoring.service_fit
    if tier == "core":
        return _points(weight, shares.core), f"Matches a core offering ('{offering}').", tier
    if tier == "adjacent":
        return _points(weight, shares.adjacent), f"Adjacent offering that needs custom scoping ('{offering}').", tier
    if tier == "out_of_scope":
        return _points(weight, shares.out_of_scope), f"Unsupported or out-of-scope request ('{offering}').", tier
    if tier == "uncatalogued":
        service = analysis.get("service_requested")
        return _points(weight, shares.uncatalogued), f"Request ('{service}') is not in the service catalog.", tier
    return 0, "No clear service requested.", tier


def evaluate_purchase_intent(analysis: Dict[str, Any], profile: BusinessProfile, weight: int) -> Tuple[int, str]:
    intent = (analysis.get("intent") or "ambiguous").lower()
    shares = profile.scoring.purchase_intent
    if intent == "high":
        return _points(weight, shares.high), "Strong buying signals: concrete use case, committed budget or firm timeline."
    if intent == "medium":
        return _points(weight, shares.medium), "Moderate interest: exploring options and pricing."
    if intent == "low":
        return _points(weight, shares.low), "Low purchase intent: exploratory or casual question."
    if intent == "spam":
        return 0, "Commercial spam or promotional solicitation."
    return 0, "Ambiguous intent: not enough business context."


def evaluate_urgency(analysis: Dict[str, Any], profile: BusinessProfile, weight: int) -> Tuple[int, str]:
    timeline = analysis.get("timeline_days")
    intent = (analysis.get("intent") or "").lower()
    urgency = profile.scoring.urgency
    if intent in ("spam", "ambiguous"):
        return 0, "No valid timeline for an ambiguous or spam submission."
    if timeline is None:
        return _points(weight, urgency.unspecified), "Timeline not stated."
    for bucket in urgency.buckets:
        if timeline <= bucket.max_days:
            unit = "day" if timeline == 1 else "days"
            return _points(weight, bucket.share), f"Wants to start within {timeline} {unit} (≤ {bucket.max_days} days)."
    return _points(weight, urgency.beyond), f"Longer horizon: {timeline} days."


def evaluate_budget_fit(analysis: Dict[str, Any], profile: BusinessProfile, weight: int) -> Tuple[int, str, Optional[float]]:
    budget = analysis.get("budget") or {}
    amount = budget.get("amount")
    currency = budget.get("currency") or profile.business.base_currency
    intent = (analysis.get("intent") or "").lower()
    base = profile.business.base_currency
    budget_fit = profile.scoring.budget_fit

    if intent in ("spam", "ambiguous"):
        return 0, "No budget credit for spam or ambiguous submissions.", None
    if not budget.get("stated") or amount is None:
        return _points(weight, budget_fit.unspecified), "Budget not stated; neutral baseline.", None

    in_base = profile.to_base_currency(amount, currency)
    stated = f"{amount:,.0f} {currency}" + ("" if currency.upper() == base else f" ≈ {in_base:,.0f} {base}")
    for tier in budget_fit.tiers:
        if in_base >= tier.min_amount:
            return _points(weight, tier.share), f"Budget {stated} meets the ≥ {tier.min_amount:,.0f} {base} tier.", in_base
    return 0, f"Budget {stated} is below every configured tier.", in_base


def evaluate_decision_authority(lead: Dict[str, Any], analysis: Dict[str, Any], profile: BusinessProfile, weight: int) -> Tuple[int, str]:
    text = " ".join(
        [
            analysis.get("contact_role") or "",
            (lead.get("contact") or {}).get("name") or "",
            lead.get("message") or "",
        ]
    ).lower()
    title = first_term(text, profile.decision_maker_titles)
    if title:
        return weight, f"Contact signals decision-making authority ('{title}')."
    return 0, "Role or authority not stated."


def evaluate_company_fit(lead: Dict[str, Any], analysis: Dict[str, Any], profile: BusinessProfile, weight: int) -> Tuple[int, str]:
    industry = (analysis.get("industry") or "").lower()
    company = lead.get("company") or {}
    size = company.get("size")
    targets = [i for i in profile.industries if i.target]
    company_text = f"{industry} {(company.get('name') or '').lower()}"

    matched = next(
        (i.name for i in targets if i.name.lower() == industry or count_terms(company_text, [i.name, *i.keywords]) > 0),
        None,
    )
    if matched:
        return weight, f"Target industry ('{matched}')."
    if size and size in profile.target_company_sizes:
        return weight, f"Target company size ('{size}')."
    return 0, "Industry or company size is outside the target profile, or unknown."


def evaluate_data_completeness(lead: Dict[str, Any], profile: BusinessProfile, weight: int) -> Tuple[int, str]:
    contact = lead.get("contact") or {}
    email = contact.get("email")
    phone = contact.get("phone")
    comp_name = (lead.get("company") or {}).get("name")

    has_email = bool(email and "@" in email)
    has_phone = bool(phone and len(phone.strip()) >= MIN_PHONE_LENGTH)
    has_company = bool(comp_name and comp_name.strip())
    shares = profile.scoring.data_completeness

    if (has_email or has_phone) and has_company:
        return _points(weight, shares.full), "Contact details and company name provided."
    if has_email or has_phone:
        return _points(weight, shares.basic), "Contact details provided, but no company name."
    return 0, "No email or phone number provided."


def _priority(total: int, intent: str, profile: BusinessProfile) -> str:
    thresholds = profile.priority_thresholds
    if intent == "spam":
        return "disqualified"
    if total >= thresholds.high:
        return "high"
    if total >= thresholds.medium:
        return "medium"
    if total >= thresholds.low:
        return "low"
    return "disqualified"


def _review_reasons(
    lead: Dict[str, Any],
    analysis: Dict[str, Any],
    profile: BusinessProfile,
    service_tier: str,
    budget_in_base: Optional[float],
) -> List[str]:
    review = profile.review
    intent = (analysis.get("intent") or "").lower()
    base = profile.business.base_currency
    contact = lead.get("contact") or {}
    reasons = []

    conf = analysis.get("confidence_score", 1.0)
    if conf < review.low_confidence_below:
        reasons.append(f"AI confidence ({conf:.2f}) is below the review threshold ({review.low_confidence_below:.2f}).")
    if budget_in_base is not None and budget_in_base >= review.large_budget_at_least:
        reasons.append(
            f"Large opportunity ({budget_in_base:,.0f} {base} ≥ {review.large_budget_at_least:,.0f} {base}); route to a senior rep."
        )
    if review.flag_out_of_scope and service_tier == "out_of_scope" and intent != "spam":
        service = (analysis.get("service_match") or {}).get("offering") or analysis.get("service_requested") or "unspecified"
        reasons.append(f"Requested service is unsupported ('{service}'); check before replying.")
    if review.flag_spam and intent == "spam":
        reasons.append("Suspected spam; automated replies suppressed.")
    if review.flag_ambiguous and intent == "ambiguous":
        reasons.append("Ambiguous message; too vague to qualify without a follow-up question.")
    if review.flag_ambiguous and intent != "spam" and not contact.get("email") and not contact.get("phone"):
        reasons.append("No email or phone number; reply on the original channel.")
    return reasons


def score_lead(
    lead: Dict[str, Any],
    analysis: Dict[str, Any],
    profile: Optional[BusinessProfile] = None,
) -> Dict[str, Any]:
    """Applies the profile's deterministic rules to a lead and its analysis."""
    profile = profile or load_default_profile()
    weights = profile.scoring.weights.model_dump()
    intent = (analysis.get("intent") or "").lower()

    s_fit, s_fit_r, service_tier = evaluate_service_fit(analysis, profile, weights["service_fit"])
    b_fit, b_fit_r, budget_in_base = evaluate_budget_fit(analysis, profile, weights["budget_fit"])
    results = {
        "service_fit": (s_fit, s_fit_r),
        "purchase_intent": evaluate_purchase_intent(analysis, profile, weights["purchase_intent"]),
        "urgency": evaluate_urgency(analysis, profile, weights["urgency"]),
        "budget_fit": (b_fit, b_fit_r),
        "decision_authority": evaluate_decision_authority(lead, analysis, profile, weights["decision_authority"]),
        "company_fit": evaluate_company_fit(lead, analysis, profile, weights["company_fit"]),
        "data_completeness": evaluate_data_completeness(lead, profile, weights["data_completeness"]),
    }

    breakdown = {dim: results[dim][0] for dim in DIMENSIONS}
    total = 0 if intent == "spam" else max(0, min(100, sum(breakdown.values())))
    reasons = _review_reasons(lead, analysis, profile, service_tier, budget_in_base)

    return {
        "lead_id": lead.get("lead_id", "unknown_lead"),
        "total_score": int(total),
        "priority": _priority(total, intent, profile),
        "score_breakdown": breakdown,
        "explanations": [
            {
                "dimension": dim,
                "points_awarded": results[dim][0],
                "max_possible": weights[dim],
                "reason": results[dim][1],
            }
            for dim in DIMENSIONS
        ],
        "requires_human_review": bool(reasons),
        "human_review_reasons": reasons,
        "scored_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    with open(ROOT_DIR / "examples" / "normalized-lead.json", "r", encoding="utf-8") as f:
        sample_lead = json.load(f)
    with open(ROOT_DIR / "examples" / "ai-analysis.json", "r", encoding="utf-8") as f:
        sample_analysis = json.load(f)

    print(json.dumps(score_lead(sample_lead, sample_analysis), indent=2, ensure_ascii=False))
