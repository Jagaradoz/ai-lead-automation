"""
test_lead_store.py
SQLite lead repository: create, read, filter, paginate, update, delete, CSV export.
"""

import csv
import io

import pytest

from scripts.lead_store import LeadStore


def record(name, priority="high", total=80, message="Need a LINE bot", engine="rules"):
    lead = {
        "lead_id": f"lead_{name}",
        "source": "website",
        "contact": {"name": name, "email": f"{name.lower()}@example.com", "phone": None},
        "company": {"name": f"{name} Co", "website": None, "size": None},
        "message": message,
        "received_at": "2026-09-25T10:00:00Z",
    }
    analysis = {"summary": f"{name} summary", "intent": "high"}
    score = {"total_score": total, "priority": priority, "requires_human_review": False}
    meta = {"engine": engine, "provider": None, "model": None, "latency_ms": 3, "fallback_reason": None}
    return lead, analysis, score, meta


@pytest.fixture
def store(tmp_path):
    return LeadStore(tmp_path / "leads.db")


def test_create_and_find_by_id(store):
    saved = store.create(*record("Ada"))
    found = store.find_by_id(saved["id"])

    assert found["id"] == saved["id"]
    assert found["lead"]["contact"]["name"] == "Ada"
    assert found["score"]["total_score"] == 80
    assert found["status"] == "new"
    assert found["meta"]["engine"] == "rules"
    assert store.find_by_id(9999) is None


def test_find_all_filters_and_paginates(store):
    store.create(*record("Ada", priority="high", total=90))
    store.create(*record("Bo", priority="low", total=30, message="just curious about pricing"))
    store.create(*record("Cy", priority="high", total=85))

    page = store.find_all(priority="high", limit=1, offset=0)
    assert page["total"] == 2
    assert len(page["items"]) == 1

    assert store.find_all(q="curious")["total"] == 1
    assert store.find_all(q="Cy Co")["total"] == 1
    assert [i["contact_name"] for i in store.find_all(sort="score")["items"]] == ["Ada", "Cy", "Bo"]


def test_update_status_and_notes(store):
    saved = store.create(*record("Ada"))
    updated = store.update(saved["id"], status="contacted", notes="Called, send proposal")

    assert updated["status"] == "contacted"
    assert updated["notes"] == "Called, send proposal"
    assert store.find_all(status="contacted")["total"] == 1

    with pytest.raises(ValueError):
        store.update(saved["id"], status="teleported")
    assert store.update(9999, status="won") is None


def test_replace_analysis_keeps_status(store):
    saved = store.create(*record("Ada"))
    store.update(saved["id"], status="qualified")
    lead, analysis, score, meta = record("Ada", priority="medium", total=50)
    replaced = store.replace_result(saved["id"], analysis, score, meta)

    assert replaced["score"]["priority"] == "medium"
    assert replaced["status"] == "qualified"


def test_delete(store):
    saved = store.create(*record("Ada"))
    assert store.delete(saved["id"]) is True
    assert store.find_by_id(saved["id"]) is None
    assert store.delete(saved["id"]) is False


def test_csv_export(store):
    store.create(*record("Ada", total=90))
    store.create(*record("Bo", total=30, priority="low"))

    rows = list(csv.DictReader(io.StringIO("".join(store.iter_csv()))))
    assert [r["contact_name"] for r in rows] == ["Bo", "Ada"]  # newest first
    assert rows[1]["total_score"] == "90"
    assert "summary" in rows[0]


def test_csv_export_neutralizes_formula_injection(store):
    lead, analysis, score, meta = record("=HYPERLINK(\"http://evil\")")
    store.create(lead, analysis, score, meta)
    store.create(*record("  +SUM(A1)"))
    rows = list(csv.DictReader(io.StringIO("".join(store.iter_csv()))))
    assert rows[0]["contact_name"].startswith("'")
    assert rows[1]["contact_name"].startswith("'=")
