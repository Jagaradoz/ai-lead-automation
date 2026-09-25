"""
rules_extractor.py
Deterministic fact extraction used when no model is configured (or as a fallback).

Everything business-specific (services, industries, titles, spam phrases, base currency)
comes from the business profile. What remains here are language patterns for budgets,
timelines and buying signals in English and Thai, which apply to any business.
"""

import logging
import re
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from scripts.business_profile import BusinessProfile
from scripts.text_match import count_terms, first_term

logger = logging.getLogger(__name__)

SHORT_MESSAGE_CHARS = 35
THAI_LANGUAGE_MIN_CHARS = 10
PROBLEM_MAX_CHARS = 200
ASAP_DAYS = 7
TODAY_DAYS = 1

# --- Budget ------------------------------------------------------------------

_CURRENCY_TOKENS = {
    "us$": "USD", "$": "USD", "usd": "USD", "dollar": "USD", "dollars": "USD",
    "s$": "SGD", "sgd": "SGD",
    "฿": "THB", "thb": "THB", "baht": "THB", "บาท": "THB",
    "€": "EUR", "eur": "EUR", "euro": "EUR", "euros": "EUR",
    "£": "GBP", "gbp": "GBP", "pound": "GBP", "pounds": "GBP",
}
_MULTIPLIERS = {
    "k": 1e3, "thousand": 1e3, "m": 1e6, "mn": 1e6, "million": 1e6,
    "พัน": 1e3, "หมื่น": 1e4, "แสน": 1e5, "ล้าน": 1e6,
}
_NUM = r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
_MULT = r"(?:\s?(thousand|million|mn|k|m|พัน|หมื่น|แสน|ล้าน)(?![a-z]))?"
_PREFIX_RE = re.compile(r"(us\$|s\$|\$|฿|€|£)\s?" + _NUM + _MULT)
_SUFFIX_RE = re.compile(_NUM + _MULT + r"\s?(thb|baht|บาท|usd|dollars?|sgd|eur|euros?|gbp|pounds?)(?![a-z])")
_BUDGET_WORD_RE = re.compile(r"(?:budget|งบประมาณ|งบ)[^\d\n]{0,20}" + _NUM + _MULT)


def _amount(number: str, multiplier: Optional[str]) -> float:
    return float(number.replace(",", "")) * _MULTIPLIERS.get(multiplier or "", 1)


def parse_budget(text_lower: str, base_currency: str) -> Optional[Tuple[float, str]]:
    """Finds a stated budget. Prefers an amount in the base currency when several are given."""
    found: List[Tuple[int, float, str]] = []
    for m in _PREFIX_RE.finditer(text_lower):
        found.append((m.start(), _amount(m.group(2), m.group(3)), _CURRENCY_TOKENS[m.group(1)]))
    for m in _SUFFIX_RE.finditer(text_lower):
        found.append((m.start(), _amount(m.group(1), m.group(2)), _CURRENCY_TOKENS[m.group(3)]))
    if not found:
        for m in _BUDGET_WORD_RE.finditer(text_lower):
            found.append((m.start(), _amount(m.group(1), m.group(2)), base_currency))
    if not found:
        return None
    found.sort(key=lambda item: item[0])
    in_base = [f for f in found if f[2] == base_currency]
    _, amount, currency = (in_base or found)[0]
    return amount, currency


# --- Timeline ----------------------------------------------------------------

_UNIT_DAYS = {
    "day": 1, "days": 1, "วัน": 1,
    "week": 7, "weeks": 7, "wk": 7, "wks": 7, "สัปดาห์": 7, "อาทิตย์": 7,
    "month": 30, "months": 30, "เดือน": 30,
}
_QTY_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12,
    "a couple of": 2, "a couple": 2, "couple of": 2, "couple": 2, "a few": 3, "few": 3,
}
_QTY = r"(\d+|" + "|".join(sorted(map(re.escape, _QTY_WORDS), key=len, reverse=True)) + r")"
_UNIT = r"(days?|weeks?|wks?|months?|วัน|สัปดาห์|อาทิตย์|เดือน)"
_CONTEXT = r"(?:(?<!\w)(?:within|in|by|next|over|under|inside|before|than)\s+|(?:ภายใน|ใน|อีก)\s*)"
_DURATION_RE = re.compile(_CONTEXT + r"(?:the\s+)?(?:next\s+)?" + _QTY + r"\s*-?\s*" + _UNIT + r"(?![a-z])")

_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4,
    "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9, "october": 10, "oct": 10, "november": 11, "nov": 11,
    "december": 12, "dec": 12,
    "มกราคม": 1, "กุมภาพันธ์": 2, "มีนาคม": 3, "เมษายน": 4, "พฤษภาคม": 5, "มิถุนายน": 6,
    "กรกฎาคม": 7, "สิงหาคม": 8, "กันยายน": 9, "ตุลาคม": 10, "พฤศจิกายน": 11, "ธันวาคม": 12,
}
_MONTH_ALT = "|".join(sorted(map(re.escape, _MONTHS), key=len, reverse=True))
_DATE_MD_RE = re.compile(r"(?<!\w)(" + _MONTH_ALT + r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?!\d)")
_DATE_DM_RE = re.compile(r"(?<!\d)(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(" + _MONTH_ALT + r")(?![a-z])")

_RELATIVE_DAYS = {
    "today": TODAY_DAYS, "tonight": TODAY_DAYS, "this afternoon": TODAY_DAYS, "this morning": TODAY_DAYS,
    "right away": TODAY_DAYS, "วันนี้": TODAY_DAYS, "tomorrow": 2, "พรุ่งนี้": 2,
    "this week": 7, "next week": 7, "สัปดาห์หน้า": 7, "next month": 30, "เดือนหน้า": 30,
}
_ASAP_TERMS = ["asap", "as soon as possible", "urgent", "urgently", "immediately", "ด่วน", "เร่งด่วน"]
_FLEXIBLE_TERMS = [
    "no rush", "not rushed", "not in a hurry", "whenever", "no deadline", "flexible timeline",
    "ไม่รีบ", "ไม่ได้รีบ", "เมื่อไหร่ก็ได้",
]


def _received_date(received_at: Optional[str]) -> date:
    if received_at:
        try:
            return datetime.fromisoformat(received_at.replace("Z", "+00:00")).date()
        except ValueError:
            logger.warning("Malformed received_at %r; measuring timelines from today", received_at)
    return datetime.now(timezone.utc).date()


def _days_until(month: int, day: int, received: date) -> Optional[int]:
    try:
        target = date(received.year, month, day)
    except ValueError:
        return None
    if target < received:
        target = date(received.year + 1, month, day)
    return (target - received).days


def parse_timeline(text_lower: str, received_at: Optional[str]) -> Optional[int]:
    """Returns the tightest stated timeline in days, or None when none is given."""
    received = _received_date(received_at)
    candidates: List[int] = []

    for m in _DURATION_RE.finditer(text_lower):
        qty = m.group(1)
        count = int(qty) if qty.isdigit() else _QTY_WORDS[qty]
        candidates.append(count * _UNIT_DAYS[m.group(2)])
    for m in _DATE_MD_RE.finditer(text_lower):
        days = _days_until(_MONTHS[m.group(1)], int(m.group(2)), received)
        if days is not None:
            candidates.append(days)
    for m in _DATE_DM_RE.finditer(text_lower):
        days = _days_until(_MONTHS[m.group(2)], int(m.group(1)), received)
        if days is not None:
            candidates.append(days)
    for phrase, days in _RELATIVE_DAYS.items():
        if phrase in text_lower:
            candidates.append(days)

    if candidates:
        return min(candidates)
    if any(term in text_lower for term in _FLEXIBLE_TERMS):
        return None
    if any(term in text_lower for term in _ASAP_TERMS):
        return ASAP_DAYS
    return None


# --- Intent ------------------------------------------------------------------

_LOW_SIGNALS = [
    "just curious", "just wondering", "just asking", "student", "school project", "research project",
    "thesis", "how much it usually costs", "how much does it usually cost", "ถามเฉยๆ",
]
_HESITANT_SIGNALS = _FLEXIBLE_TERMS + [
    "budget is tight", "tight budget", "affordabl", "cheap", "low cost", "simple way",
    "just exploring", "exploring options", "ยังไม่แน่ใจ",
]
_COMMITMENT_SIGNALS = [
    "approved", "allocated", "signed off", "urgent", "asap", "as soon as possible", "immediately",
    "today", "this afternoon", "rfp", "request for proposal", "deadline", "need to launch",
    "need this live", "go live", "ready to start", "ด่วน", "อนุมัติ",
]


def classify_intent(
    msg_lower: str,
    is_spam: bool,
    has_service: bool,
    budget: Optional[Tuple[float, str]],
    timeline_days: Optional[int],
) -> str:
    if is_spam:
        return "spam"
    if len(msg_lower.strip()) < SHORT_MESSAGE_CHARS and not has_service:
        return "ambiguous"
    if any(s in msg_lower for s in _LOW_SIGNALS):
        return "low"
    if any(s in msg_lower for s in _HESITANT_SIGNALS):
        return "medium"
    if any(s in msg_lower for s in _COMMITMENT_SIGNALS):
        return "high"
    if budget and timeline_days is not None and timeline_days <= 30:
        return "high"
    if not has_service and not budget and timeline_days is None:
        return "low"
    return "medium"


# --- Profile-driven detection --------------------------------------------------

def match_service(text_lower: str, profile: BusinessProfile) -> Tuple[Optional[str], str]:
    """Returns (offering, tier) for the catalog service with the most keyword hits."""
    tier_rank = {"core": 0, "adjacent": 1, "out_of_scope": 2}
    best = max(
        ((count_terms(text_lower, s.keywords + [s.name.lower()]), -tier_rank[s.tier], s) for s in profile.services),
        key=lambda item: (item[0], item[1]),
        default=(0, 0, None),
    )
    hits, _, service = best
    if service is None or hits == 0:
        return None, "none"
    return service.name, service.tier


def detect_industry(text_lower: str, profile: BusinessProfile) -> Optional[str]:
    best = max(
        ((count_terms(text_lower, [i.name.lower(), *i.keywords]), -idx, i.name) for idx, i in enumerate(profile.industries)),
        default=(0, 0, None),
    )
    return best[2] if best[0] > 0 else None


def _confidence(intent: str, industry: Optional[str], budget, timeline_days) -> float:
    if intent == "spam":
        return 0.95
    if intent == "ambiguous":
        return 0.55
    if industry and budget and timeline_days is not None:
        return 0.95
    if industry and (budget or timeline_days is not None):
        return 0.88
    return 0.60


def _problem(message: str) -> str:
    text = " ".join(message.split())
    return text if len(text) <= PROBLEM_MAX_CHARS else text[: PROBLEM_MAX_CHARS - 1].rstrip() + "…"


def _summary(intent: str, industry: Optional[str], service: Optional[str], budget, timeline_days) -> str:
    if intent == "spam":
        return "Looks like promotional spam."
    if intent == "ambiguous":
        return "Too little detail to qualify; ask what they need."
    parts = [f"{(industry or 'Unknown industry').capitalize()} lead asking about {service or 'unspecified needs'}"]
    if budget:
        parts.append(f"budget {budget[0]:,.0f} {budget[1]}")
    if timeline_days is not None:
        unit = "day" if timeline_days == 1 else "days"
        parts.append(f"wants to start within {timeline_days} {unit}")
    return ", ".join(parts) + "."


def extract_with_rules(lead: Dict[str, Any], profile: BusinessProfile) -> Dict[str, Any]:
    """Builds a LeadAnalysis from the lead text using the profile and language patterns."""
    message = lead.get("message") or ""
    msg_lower = message.lower()
    contact = lead.get("contact") or {}
    company = lead.get("company") or {}
    company_lower = (company.get("name") or "").lower()

    thai_chars = sum(1 for ch in message if "฀" <= ch <= "๿")
    language = "th" if thai_chars > THAI_LANGUAGE_MIN_CHARS else "en"
    is_spam = any(phrase in msg_lower for phrase in profile.spam_phrases)

    offering, tier = match_service(msg_lower, profile)
    budget = parse_budget(msg_lower, profile.business.base_currency)
    timeline_days = parse_timeline(msg_lower, lead.get("received_at"))
    intent = classify_intent(msg_lower, is_spam, offering is not None, budget, timeline_days)
    industry = detect_industry(f"{msg_lower} {company_lower}", profile)
    role = first_term(f"{(contact.get('name') or '').lower()} {msg_lower}", profile.decision_maker_titles)

    if intent in ("spam", "ambiguous"):
        offering, tier = None, "none"

    missing = []
    if not budget:
        missing.append("explicit_budget")
    if timeline_days is None and intent != "spam":
        missing.append("implementation_deadline")
    if not contact.get("phone"):
        missing.append("phone_number")
    if not company.get("name"):
        missing.append("company_name")

    return {
        "industry": industry,
        "service_requested": offering,
        "service_match": {"offering": offering, "tier": tier},
        "problem": None if intent in ("spam", "ambiguous") else _problem(message),
        "contact_role": role,
        "budget": {
            "amount": budget[0] if budget else None,
            "currency": budget[1] if budget else None,
            "stated": bool(budget),
        },
        "timeline_days": timeline_days,
        "intent": intent,
        "language": language,
        "summary": _summary(intent, industry, offering, budget, timeline_days),
        "missing_information": missing,
        "confidence_score": _confidence(intent, industry, budget, timeline_days),
    }

