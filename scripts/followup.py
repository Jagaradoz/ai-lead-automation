"""
followup.py
Turns a scored lead into a next step: who owns it, how fast to respond, and a
first reply drafted in the customer's language. Deterministic (no model call),
so every lead gets a usable draft even when no model is configured.
"""

from typing import Any, Dict, List, Optional

from scripts.business_profile import BusinessProfile

# Response playbook per priority. Response targets are in minutes.
ROUTES: Dict[str, Dict[str, Any]] = {
    "high": {
        "owner": "Senior sales rep",
        "action": "Call or message today",
        "respond_within_min": 60,
        "channel_alert": True,
    },
    "medium": {
        "owner": "Sales team queue",
        "action": "Reply with discovery questions",
        "respond_within_min": 24 * 60,
        "channel_alert": False,
    },
    "low": {
        "owner": "Nurture sequence",
        "action": "Send info pack, follow up in a week",
        "respond_within_min": 72 * 60,
        "channel_alert": False,
    },
    "disqualified": {
        "owner": "No owner",
        "action": "Do not reply automatically",
        "respond_within_min": None,
        "channel_alert": False,
    },
}
REVIEW_OWNER = "Sales lead (review first)"

_QUESTIONS = {
    "en": {
        "budget": "What budget range do you have in mind?",
        "timeline": "When would you like this to be live?",
        "company": "Could you tell us a bit about your company and team size?",
        "contact": "What's the best phone number or email to reach you?",
        "decision": "Who else will be involved in the decision?",
    },
    "th": {
        "budget": "งบประมาณที่วางไว้ประมาณเท่าไหร่ครับ/คะ",
        "timeline": "ต้องการให้ระบบใช้งานได้ภายในเมื่อไหร่ครับ/คะ",
        "company": "ขอทราบข้อมูลบริษัทและขนาดทีมคร่าว ๆ ได้ไหมครับ/คะ",
        "contact": "สะดวกให้ติดต่อกลับทางเบอร์โทรหรืออีเมลไหนครับ/คะ",
        "decision": "มีผู้ร่วมตัดสินใจท่านอื่นอีกไหมครับ/คะ",
    },
}
_MAX_QUESTIONS = 3


def _missing_keys(analysis: Dict[str, Any], lead: Dict[str, Any]) -> List[str]:
    keys = []
    if not (analysis.get("budget") or {}).get("stated"):
        keys.append("budget")
    if analysis.get("timeline_days") is None:
        keys.append("timeline")
    if not (lead.get("company") or {}).get("name"):
        keys.append("company")
    contact = lead.get("contact") or {}
    if not contact.get("email") and not contact.get("phone"):
        keys.append("contact")
    if not analysis.get("contact_role"):
        keys.append("decision")
    return keys[:_MAX_QUESTIONS]


def route_lead(score: Dict[str, Any]) -> Dict[str, Any]:
    priority = score.get("priority") or "disqualified"
    route = dict(ROUTES.get(priority, ROUTES["disqualified"]))
    route["priority"] = priority
    if score.get("requires_human_review") and priority != "disqualified":
        route["owner"] = REVIEW_OWNER
    return route


def _draft_en(name: str, service: Optional[str], business: str, questions: List[str], priority: str) -> str:
    topic = f"about {service}" if service else "and for reaching out"
    lines = [f"Hi {name},", "", f"Thank you for contacting {business} {topic}."]
    if priority == "high":
        lines.append("This sounds like a great fit. Could we set up a 20-minute call this week to go through your setup?")
    else:
        lines.append("We'd be glad to help and want to suggest the right option for you.")
    if questions:
        lines += ["", "A few quick questions so we can prepare:"] + [f"- {q}" for q in questions]
    lines += ["", "Best regards,", business]
    return "\n".join(lines)


def _draft_th(name: str, service: Optional[str], business: str, questions: List[str], priority: str) -> str:
    topic = f"เรื่อง {service}" if service else ""
    lines = [f"สวัสดีครับ/ค่ะ คุณ{name}", "", f"ขอบคุณที่ติดต่อ {business} {topic}".rstrip()]
    if priority == "high":
        lines.append("โปรเจกต์นี้ตรงกับบริการของเราครับ/ค่ะ สะดวกนัดคุยสั้น ๆ 20 นาทีภายในสัปดาห์นี้ไหมครับ/คะ")
    else:
        lines.append("ทีมงานยินดีช่วยแนะนำแพ็กเกจที่เหมาะกับคุณครับ/ค่ะ")
    if questions:
        lines += ["", "ขอสอบถามข้อมูลเพิ่มเติมเล็กน้อย:"] + [f"- {q}" for q in questions]
    lines += ["", "ขอบคุณครับ/ค่ะ", business]
    return "\n".join(lines)


def draft_reply(
    lead: Dict[str, Any], analysis: Dict[str, Any], score: Dict[str, Any], profile: BusinessProfile
) -> Optional[Dict[str, Any]]:
    """Returns a reply draft, or None when the lead should not get an automatic reply."""
    priority = score.get("priority") or "disqualified"
    if priority == "disqualified":
        return None
    language = "th" if analysis.get("language") == "th" else "en"
    name = ((lead.get("contact") or {}).get("name") or "").strip() or ("ลูกค้า" if language == "th" else "there")
    service = (analysis.get("service_match") or {}).get("offering") or analysis.get("service_requested")
    questions = [_QUESTIONS[language][k] for k in _missing_keys(analysis, lead)]
    writer = _draft_th if language == "th" else _draft_en
    return {
        "language": language,
        "subject": f"Re: {service}" if service else f"Your enquiry to {profile.business.name}",
        "body": writer(name, service, profile.business.name, questions, priority),
    }


def build_followup(
    lead: Dict[str, Any], analysis: Dict[str, Any], score: Dict[str, Any], profile: BusinessProfile
) -> Dict[str, Any]:
    return {"route": route_lead(score), "reply": draft_reply(lead, analysis, score, profile)}
