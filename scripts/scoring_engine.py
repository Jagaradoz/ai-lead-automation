#!/usr/bin/env python3
"""
scoring_engine.py
Deterministic Lead Scoring Engine for AI Lead Automation.
Computes explainable, rule-based dimensional scores from Canonical Lead and AI Analysis objects.
Produces strictly conformant LeadScoreResult objects matching schemas/lead-score.schema.json.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT_DIR / "config" / "scoring.example.json"


def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    path = config_path or DEFAULT_CONFIG_PATH
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_to_thb(amount: Optional[float], currency: Optional[str]) -> Optional[float]:
    """Converts stated currency to THB equivalent for standardized threshold comparison."""
    if amount is None:
        return None
    curr = (currency or "THB").upper().strip()
    if curr == "THB":
        return float(amount)
    elif curr == "USD":
        return float(amount) * 35.0
    elif curr == "EUR":
        return float(amount) * 38.0
    elif curr == "GBP":
        return float(amount) * 44.0
    elif curr == "SGD":
        return float(amount) * 26.0
    return float(amount)


def evaluate_service_fit(analysis: Dict[str, Any]) -> Tuple[int, str]:
    service = (analysis.get("service_requested") or "").lower()
    problem = (analysis.get("problem") or "").lower()
    intent = (analysis.get("intent") or "").lower()
    combined = f"{service} {problem}"

    if not service or intent in ["ambiguous", "spam"]:
        return 0, "No clear or identifiable automation service requested."

    # Out of scope / unsupported (checked first)
    unsupported_keywords = [
        "hardware", "motherboard", "server repair", "power supply", "seo",
        "backlink", "google ranking", "mobile app development"
    ]
    for kw in unsupported_keywords:
        if kw in combined:
            return 0, f"Unsupported or out-of-scope domain detected ('{kw}')."

    # Exact core offerings
    core_keywords = [
        "line ai", "line bot", "crm", "workflow automation", "lead qualification",
        "appointment reminder", "lead intake", "customer service bot", "chat bot", "chatbot"
    ]
    for kw in core_keywords:
        if kw in combined:
            return 25, f"Direct match for core automation offerings ('{kw}')."

    # Adjacent offerings
    adjacent_keywords = [
        "shopify", "api integration", "data pipeline", "webhook", "sheets",
        "google sheet", "hubspot", "compliance"
    ]
    for kw in adjacent_keywords:
        if kw in combined:
            return 15, f"Adjacent service offering requiring custom scoping ('{kw}')."

    return 5, "General or uncataloged automation inquiry."


def evaluate_purchase_intent(analysis: Dict[str, Any]) -> Tuple[int, str]:
    intent = (analysis.get("intent") or "ambiguous").lower()
    if intent == "high":
        return 20, "Strong buying signals: specific use case, approved budget, or clear timeline."
    elif intent == "medium":
        return 10, "Moderate interest: general inquiry seeking options and pricing."
    elif intent == "low":
        return 0, "Low purchase intent: exploratory inquiry or casual question."
    elif intent == "spam":
        return 0, "Commercial spam or promotional solicitation."
    else:  # ambiguous
        return 0, "Ambiguous intent: lacks actionable business context."


def evaluate_urgency(analysis: Dict[str, Any]) -> Tuple[int, str]:
    timeline = analysis.get("timeline_days")
    intent = (analysis.get("intent") or "").lower()
    if intent in ["spam", "ambiguous"]:
        return 0, "No valid timeline associated with ambiguous/spam submission."

    if timeline is not None:
        if timeline <= 30:
            return 20, f"High urgency: requested launch within {timeline} days (<= 30 days)."
        elif timeline <= 90:
            return 12, f"Medium urgency: requested launch within {timeline} days (31-90 days)."
        else:
            return 5, f"Low urgency: launch horizon extends beyond 90 days ({timeline} days)."
    return 5, "Timeline unspecified; assigned neutral low-urgency points."


def evaluate_budget_fit(analysis: Dict[str, Any]) -> Tuple[int, str, Optional[float]]:
    budget = analysis.get("budget") or {}
    stated = budget.get("stated", False)
    amount = budget.get("amount")
    currency = budget.get("currency")
    intent = (analysis.get("intent") or "").lower()

    if intent in ["spam", "ambiguous"]:
        return 0, "No budget awarded for spam or ambiguous submissions.", None

    if not stated or amount is None:
        return 10, "Budget not explicitly stated; awarded neutral baseline points.", None

    amount_thb = normalize_to_thb(amount, currency)
    if amount_thb >= 100000:
        return 20, f"Stated budget ({amount:,.0f} {currency or 'THB'} ~ {amount_thb:,.0f} THB) meets target/enterprise tier (>= 100k THB).", amount_thb
    elif amount_thb >= 40000:
        return 15, f"Stated budget ({amount:,.0f} {currency or 'THB'} ~ {amount_thb:,.0f} THB) fits starter/SMB automation package (40k-99k THB).", amount_thb
    else:
        return 5, f"Stated budget ({amount:,.0f} {currency or 'THB'} ~ {amount_thb:,.0f} THB) is below standard minimum engagement threshold (< 40k THB).", amount_thb


def evaluate_decision_authority(lead: Dict[str, Any], analysis: Dict[str, Any]) -> Tuple[int, str]:
    name = (lead.get("contact", {}).get("name") or "").lower()
    msg = (lead.get("message") or "").lower()

    exec_patterns = [
        r"\bdr\b\.?", r"\bceo\b", r"\bfounder\b", r"\bdirector\b", r"\bowner\b",
        r"\bmanaging director\b", r"\bvp\b", r"\bpresident\b", r"\bmanager\b",
        r"\bเจ้าของ\b", r"\bผู้จัดการ\b", r"\bกรรมการ\b"
    ]

    for pat in exec_patterns:
        if re.search(pat, name) or re.search(pat, msg):
            return 5, "Contact indicated executive, founder, or managerial authority."

    return 0, "Authority level or executive title not stated in initial contact."


def evaluate_company_fit(lead: Dict[str, Any], analysis: Dict[str, Any]) -> Tuple[int, str]:
    industry = (analysis.get("industry") or "").lower()
    company = lead.get("company") or {}
    comp_name = (company.get("name") or "").lower()
    size = company.get("size")

    target_verticals = [
        "restaurant", "healthcare", "dental", "clinic", "ecommerce", "retail",
        "apparel", "logistics", "financial", "finance", "hospitality", "hotel", "resort"
    ]

    is_target_vertical = any(v in industry or v in comp_name for v in target_verticals)
    is_target_size = size in ["11-50", "50+"]

    if is_target_vertical or is_target_size:
        matched = industry or (size and f"size {size}") or "target profile"
        return 5, f"Matches priority target vertical or qualified organization scale ('{matched}')."

    return 0, "Non-target vertical or company profile unverified."


def evaluate_data_completeness(lead: Dict[str, Any]) -> Tuple[int, str]:
    contact = lead.get("contact") or {}
    email = contact.get("email")
    phone = contact.get("phone")
    company = lead.get("company") or {}
    comp_name = company.get("name")

    has_email = bool(email and "@" in email)
    has_phone = bool(phone and len(phone.strip()) >= 7)
    has_company = bool(comp_name and len(comp_name.strip()) > 0)

    if (has_email or has_phone) and has_company:
        return 5, "Complete submission with verified contact details and company identity."
    elif has_email or has_phone:
        return 3, "Basic contact info provided (email or phone) without full company details."
    else:
        return 0, "Incomplete contact information; neither direct email nor phone provided."


def score_lead(lead: Dict[str, Any], analysis: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Executes deterministic lead qualification rules against CanonicalLead and LeadAnalysis.
    Returns conformant LeadScoreResult.
    """
    cfg = config or load_config()

    # Dimension calculations
    s_fit, s_fit_r = evaluate_service_fit(analysis)
    p_intent, p_intent_r = evaluate_purchase_intent(analysis)
    urg, urg_r = evaluate_urgency(analysis)
    b_fit, b_fit_r, budget_thb = evaluate_budget_fit(analysis)
    d_auth, d_auth_r = evaluate_decision_authority(lead, analysis)
    c_fit, c_fit_r = evaluate_company_fit(lead, analysis)
    d_comp, d_comp_r = evaluate_data_completeness(lead)

    breakdown = {
        "service_fit": s_fit,
        "purchase_intent": p_intent,
        "urgency": urg,
        "budget_fit": b_fit,
        "decision_authority": d_auth,
        "company_fit": c_fit,
        "data_completeness": d_comp,
    }

    raw_total = sum(breakdown.values())

    # Spam check override
    intent = (analysis.get("intent") or "").lower()
    if intent == "spam":
        raw_total = 0

    total_score = max(0, min(100, raw_total))

    # Priority bracket mapping
    thresholds = cfg.get("priority_thresholds", {"high": 75, "medium": 45, "low": 20, "disqualified": 0})
    if intent == "spam":
        priority = "disqualified"
    elif total_score >= thresholds.get("high", 75):
        priority = "high"
    elif total_score >= thresholds.get("medium", 45):
        priority = "medium"
    elif total_score >= thresholds.get("low", 20):
        priority = "low"
    else:
        priority = "disqualified"

    # Explanations
    explanations = [
        {"dimension": "service_fit", "points_awarded": s_fit, "max_possible": 25, "reason": s_fit_r},
        {"dimension": "purchase_intent", "points_awarded": p_intent, "max_possible": 20, "reason": p_intent_r},
        {"dimension": "urgency", "points_awarded": urg, "max_possible": 20, "reason": urg_r},
        {"dimension": "budget_fit", "points_awarded": b_fit, "max_possible": 20, "reason": b_fit_r},
        {"dimension": "decision_authority", "points_awarded": d_auth, "max_possible": 5, "reason": d_auth_r},
        {"dimension": "company_fit", "points_awarded": c_fit, "max_possible": 5, "reason": c_fit_r},
        {"dimension": "data_completeness", "points_awarded": d_comp, "max_possible": 5, "reason": d_comp_r},
    ]

    # Human review triggers
    review_reasons = []
    triggers = cfg.get("human_review_triggers", {})

    conf = analysis.get("confidence_score", 1.0)
    conf_thresh = triggers.get("low_ai_confidence", {}).get("threshold", 0.65)
    if conf < conf_thresh:
        review_reasons.append(f"AI extraction confidence ({conf:.2f}) below safety threshold ({conf_thresh:.2f}).")

    large_budget_thresh = triggers.get("large_opportunity_budget_thb", {}).get("threshold", 300000)
    if budget_thb is not None and budget_thb >= large_budget_thresh:
        review_reasons.append(f"Large opportunity value ({budget_thb:,.0f} THB >= {large_budget_thresh:,.0f} THB) flags executive review.")

    if s_fit == 0 and intent != "spam":
        service_name = analysis.get("service_requested") or "unspecified service"
        review_reasons.append(f"Out-of-scope or unsupported service request ('{service_name}') requires manual review.")

    if intent == "spam":
        review_reasons.append("Suspected promotional spam; automated outbound messaging suppressed.")

    if intent == "ambiguous" or (lead.get("contact", {}).get("email") is None and lead.get("contact", {}).get("phone") is None):
        review_reasons.append("Ambiguous message or insufficient contact info requires manual lead triage.")

    scored_result = {
        "lead_id": lead.get("lead_id", "unknown_lead"),
        "total_score": int(total_score),
        "priority": priority,
        "score_breakdown": breakdown,
        "explanations": explanations,
        "requires_human_review": len(review_reasons) > 0,
        "human_review_reasons": review_reasons,
        "scored_at": datetime.now(timezone.utc).isoformat(),
    }

    return scored_result


if __name__ == "__main__":
    lead_file = ROOT_DIR / "examples" / "normalized-lead.json"
    analysis_file = ROOT_DIR / "examples" / "ai-analysis.json"

    with open(lead_file, "r", encoding="utf-8") as f:
        sample_lead = json.load(f)
    with open(analysis_file, "r", encoding="utf-8") as f:
        sample_analysis = json.load(f)

    result = score_lead(sample_lead, sample_analysis)
    print(json.dumps(result, indent=2, ensure_ascii=False))
