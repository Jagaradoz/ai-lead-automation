"""
seed_demo_leads.py
Fills the inbox with realistic demo leads so the Dashboard has something to show.
Each lead runs through the real pipeline (normalize -> analyze -> score) and is
tagged meta.demo = true. Arrival times are spread over recent days and a sales
outcome is simulated from the priority, so the win-rate charts have data.

Usage:
    python -m scripts.seed_demo_leads                 # built-in Thai/English scenarios
    python -m scripts.seed_demo_leads --llm 20        # plus 20 leads written by your configured model
    python -m scripts.seed_demo_leads --clear         # remove demo leads only
"""

import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from scripts.ai_extractor import run_analysis
from scripts.business_profile import ProfileStore
from scripts.lead_store import LeadStore
from scripts.llm.providers import ExtractionRequest, ProviderError
from scripts.llm.settings_store import SettingsStore, build_provider
from scripts.normalize import normalize_lead
from scripts.paths import ROOT_DIR, data_dir
from scripts.scoring_engine import score_lead

SCENARIOS_PATH = ROOT_DIR / "evaluation" / "datasets" / "demo-leads.json"
SPREAD_DAYS = 14
SEED = 7
SOURCES = ("website", "line", "facebook", "email")

# Simulated sales outcome per priority: (status, weight). Demo only.
OUTCOMES = {
    "high": [("won", 45), ("lost", 15), ("qualified", 20), ("contacted", 15), ("new", 5)],
    "medium": [("won", 20), ("lost", 30), ("contacted", 30), ("new", 20)],
    "low": [("won", 5), ("lost", 45), ("contacted", 20), ("new", 30)],
    "disqualified": [("spam", 60), ("lost", 20), ("new", 20)],
}

GENERATION_SCHEMA = {
    "type": "object",
    "properties": {
        "leads": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "enum": list(SOURCES)},
                    "name": {"type": "string"},
                    "company": {"type": ["string", "null"]},
                    "email": {"type": ["string", "null"]},
                    "phone": {"type": ["string", "null"]},
                    "size": {"type": ["string", "null"], "enum": ["1-10", "11-50", "50+", None]},
                    "message": {"type": "string"},
                },
                "required": ["source", "name", "company", "email", "phone", "size", "message"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["leads"],
    "additionalProperties": False,
}


def generate_with_model(count: int, business: str) -> List[Dict[str, Any]]:
    settings = SettingsStore().load()
    if not settings.is_configured:
        raise SystemExit("No model is set up. Configure one in Settings > Model, or run without --llm.")
    request = ExtractionRequest(
        name="demo_leads",
        system=(
            "You write realistic inbound sales enquiries for testing a lead-triage system. "
            "Use fictional people and companies with .example email domains."
        ),
        user=(
            f"The business: {business}\n\n"
            f"Write {count} varied enquiries. Mix Thai and English. Include strong buyers with budget and "
            "timeline, vague or curious ones, out-of-scope requests, and a few spam messages. Vary tone, "
            "length and how much contact info is given."
        ),
        schema=GENERATION_SCHEMA,
    )
    try:
        return build_provider(settings).extract(request)["leads"][:count]
    except ProviderError as err:
        raise SystemExit(f"The model could not generate leads: {err}")


def to_payload(item: Dict[str, Any], received_at: datetime, index: int) -> Dict[str, Any]:
    return {
        "lead_id": f"demo_{received_at:%Y%m%d}_{index:03d}",
        "source": item.get("source") if item.get("source") in SOURCES else "website",
        "contact": {"name": item.get("name") or "Unknown", "email": item.get("email"), "phone": item.get("phone")},
        "company": {"name": item.get("company"), "website": None, "size": item.get("size")},
        "message": item["message"],
        "received_at": received_at.isoformat(),
    }


def pick_status(rng: random.Random, priority: str) -> str:
    options = OUTCOMES.get(priority, OUTCOMES["low"])
    return rng.choices([s for s, _ in options], weights=[w for _, w in options])[0]


def clear_demo(store: LeadStore) -> int:
    removed = 0
    for lead_id in store.all_ids():
        record = store.find_by_id(lead_id)
        if record and record["meta"].get("demo"):
            removed += store.delete(lead_id)
    return removed


def seed(items: List[Dict[str, Any]], store: LeadStore) -> int:
    rng = random.Random(SEED)
    profile = ProfileStore().load()
    settings = SettingsStore().load()
    now = datetime.now(timezone.utc)
    for index, item in enumerate(items):
        received_at = now - timedelta(days=rng.uniform(0, SPREAD_DAYS - 1), minutes=rng.randint(0, 600))
        lead = normalize_lead(to_payload(item, received_at, index))
        analysis, meta = run_analysis(lead, profile, settings)
        score = score_lead(lead, analysis, profile)
        store.create(
            lead, analysis, score, {**meta, "demo": True},
            created_at=received_at.isoformat(), status=pick_status(rng, score["priority"]),
        )
        print(f"  {score['total_score']:>3} {score['priority']:<12} {lead['contact']['name']}")
    return len(items)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--llm", type=int, default=0, metavar="N", help="Also generate N leads with the configured model")
    parser.add_argument("--clear", action="store_true", help="Remove demo leads and exit")
    args = parser.parse_args()

    store = LeadStore(data_dir() / "leads.db")
    if args.clear:
        print(f"Removed {clear_demo(store)} demo leads.")
        return

    items = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    if args.llm > 0:
        items += generate_with_model(args.llm, ProfileStore().load().business.description)
    print(f"Seeding {len(items)} demo leads:")
    print(f"Done: {seed(items, store)} leads added. Remove them with --clear.")


if __name__ == "__main__":
    main()
