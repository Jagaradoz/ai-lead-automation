"""
lead_store.py
SQLite repository for processed leads (the inbox).
Each row keeps the canonical lead, the analysis, the score and which engine produced them,
plus the sales status and notes a person adds while working the lead.
"""

import csv
import io
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from scripts.paths import data_dir

STATUSES = ("new", "contacted", "qualified", "won", "lost", "spam")
PRIORITIES = ("high", "medium", "low", "disqualified")
MAX_PAGE_SIZE = 200
MAX_NOTES_CHARS = 5000
_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "|", "\t", "\r", "\n", "\uff1d", "\uff0b", "\uff0d", "\uff20")
SQLITE_TIMEOUT_S = 15
STATS_DAYS = 14
MAX_STATS_DAYS = 90

_SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_ref TEXT NOT NULL,
    received_at TEXT,
    source TEXT,
    contact_name TEXT,
    company_name TEXT,
    message TEXT,
    summary TEXT,
    lead_json TEXT NOT NULL,
    analysis_json TEXT NOT NULL,
    score_json TEXT NOT NULL,
    meta_json TEXT NOT NULL,
    total_score INTEGER NOT NULL,
    priority TEXT NOT NULL,
    requires_review INTEGER NOT NULL DEFAULT 0,
    engine TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_leads_priority ON leads(priority);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_created ON leads(created_at);
"""

_LIST_COLUMNS = (
    "id, lead_ref, received_at, source, contact_name, company_name, summary, "
    "total_score, priority, requires_review, engine, status, created_at, updated_at"
)
_CSV_COLUMNS = [
    "id", "received_at", "source", "contact_name", "company_name", "email", "phone",
    "total_score", "priority", "status", "requires_review", "engine", "summary", "message", "notes",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _median(values: list) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    return float(ordered[mid]) if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def _csv_safe(value: Any) -> Any:
    """Prevents spreadsheet formula injection from lead-supplied text."""
    if isinstance(value, str) and value.lstrip(" ").startswith(_CSV_FORMULA_PREFIXES):
        return "'" + value
    return value


class LeadStore:
    def __init__(self, path: Optional[Path] = None):
        self._path = path or data_dir() / "leads.db"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path, timeout=SQLITE_TIMEOUT_S)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _detail(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "status": row["status"],
            "notes": row["notes"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "lead": json.loads(row["lead_json"]),
            "analysis": json.loads(row["analysis_json"]),
            "score": json.loads(row["score_json"]),
            "meta": json.loads(row["meta_json"]),
        }

    @staticmethod
    def _summary_row(row: sqlite3.Row) -> Dict[str, Any]:
        item = dict(row)
        item["requires_review"] = bool(item["requires_review"])
        return item

    def create(
        self,
        lead: Dict[str, Any],
        analysis: Dict[str, Any],
        score: Dict[str, Any],
        meta: Dict[str, Any],
        created_at: Optional[str] = None,
        status: str = "new",
    ) -> Dict[str, Any]:
        """Saves a processed lead. `created_at`/`status` let demo seeding backdate leads."""
        if status not in STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(STATUSES)}.")
        now = created_at or _now()
        contact = lead.get("contact") or {}
        company = lead.get("company") or {}
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO leads (lead_ref, received_at, source, contact_name, company_name, message, summary,
                   lead_json, analysis_json, score_json, meta_json, total_score, priority, requires_review, engine,
                   status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    lead.get("lead_id", ""),
                    lead.get("received_at"),
                    lead.get("source"),
                    contact.get("name"),
                    company.get("name"),
                    lead.get("message", ""),
                    analysis.get("summary"),
                    json.dumps(lead, ensure_ascii=False),
                    json.dumps(analysis, ensure_ascii=False),
                    json.dumps(score, ensure_ascii=False),
                    json.dumps(meta, ensure_ascii=False),
                    int(score.get("total_score", 0)),
                    score.get("priority", "disqualified"),
                    int(bool(score.get("requires_human_review"))),
                    meta.get("engine"),
                    status,
                    now,
                    now,
                ),
            )
            new_id = cur.lastrowid
        return self.find_by_id(new_id)

    def find_by_id(self, lead_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        return self._detail(row) if row else None

    def find_all(
        self,
        priority: Optional[str] = None,
        status: Optional[str] = None,
        q: Optional[str] = None,
        sort: str = "recent",
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        clauses, params = [], []
        if priority:
            clauses.append("priority = ?")
            params.append(priority)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if q:
            like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            clauses.append(
                "(contact_name LIKE ? ESCAPE '\\' OR company_name LIKE ? ESCAPE '\\' "
                "OR message LIKE ? ESCAPE '\\' OR summary LIKE ? ESCAPE '\\')"
            )
            params.extend([like] * 4)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        order = "total_score DESC, id DESC" if sort == "score" else "id DESC"
        limit = max(1, min(limit, MAX_PAGE_SIZE))
        offset = max(0, offset)

        with self._connect() as conn:
            total = conn.execute(f"SELECT COUNT(*) FROM leads {where}", params).fetchone()[0]
            rows = conn.execute(
                f"SELECT {_LIST_COLUMNS} FROM leads {where} ORDER BY {order} LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
            counts = dict(conn.execute("SELECT status, COUNT(*) FROM leads GROUP BY status").fetchall())
        return {
            "items": [self._summary_row(r) for r in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
            "status_counts": counts,
        }

    def update(self, lead_id: int, status: Optional[str] = None, notes: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if status is not None and status not in STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(STATUSES)}.")
        if notes is not None and len(notes) > MAX_NOTES_CHARS:
            raise ValueError(f"Notes are limited to {MAX_NOTES_CHARS} characters.")
        sets, params = ["updated_at = ?"], [_now()]
        if status is not None:
            sets.append("status = ?")
            params.append(status)
        if notes is not None:
            sets.append("notes = ?")
            params.append(notes)
        with self._connect() as conn:
            cur = conn.execute(f"UPDATE leads SET {', '.join(sets)} WHERE id = ?", [*params, lead_id])
            if cur.rowcount == 0:
                return None
        return self.find_by_id(lead_id)

    def replace_result(
        self, lead_id: int, analysis: Dict[str, Any], score: Dict[str, Any], meta: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Stores a new analysis/score for an existing lead (rescore or re-analyze)."""
        with self._connect() as conn:
            cur = conn.execute(
                """UPDATE leads SET analysis_json = ?, score_json = ?, meta_json = ?, summary = ?,
                   total_score = ?, priority = ?, requires_review = ?, engine = ?, updated_at = ?
                   WHERE id = ?""",
                (
                    json.dumps(analysis, ensure_ascii=False),
                    json.dumps(score, ensure_ascii=False),
                    json.dumps(meta, ensure_ascii=False),
                    analysis.get("summary"),
                    int(score.get("total_score", 0)),
                    score.get("priority", "disqualified"),
                    int(bool(score.get("requires_human_review"))),
                    meta.get("engine"),
                    _now(),
                    lead_id,
                ),
            )
            if cur.rowcount == 0:
                return None
        return self.find_by_id(lead_id)

    def stats(self, days: int = STATS_DAYS) -> Dict[str, Any]:
        """Aggregates for the dashboard: totals, mixes, daily volume and win rate by channel."""
        days = max(1, min(days, MAX_STATS_DAYS))
        since = (datetime.now(timezone.utc) - timedelta(days=days - 1)).date().isoformat()
        with self._connect() as conn:
            total, avg_score, review = conn.execute(
                "SELECT COUNT(*), AVG(total_score), SUM(requires_review) FROM leads"
            ).fetchone()
            by_priority = dict(conn.execute("SELECT priority, COUNT(*) FROM leads GROUP BY priority").fetchall())
            by_status = dict(conn.execute("SELECT status, COUNT(*) FROM leads GROUP BY status").fetchall())
            by_day = dict(conn.execute(
                "SELECT substr(created_at, 1, 10) AS d, COUNT(*) FROM leads WHERE d >= ? GROUP BY d", (since,)
            ).fetchall())
            sources = conn.execute(
                """SELECT COALESCE(source, 'api') AS src, COUNT(*) AS n,
                   SUM(status = 'won') AS won, SUM(status IN ('won', 'lost')) AS closed,
                   AVG(total_score) AS avg_score
                   FROM leads GROUP BY src ORDER BY n DESC"""
            ).fetchall()
            latencies = [
                row[0] for row in conn.execute(
                    "SELECT json_extract(meta_json, '$.latency_ms') FROM leads "
                    "WHERE json_extract(meta_json, '$.latency_ms') IS NOT NULL"
                )
            ]
        start = datetime.fromisoformat(since)
        daily = []
        for i in range(days):
            day = (start + timedelta(days=i)).date().isoformat()
            daily.append({"date": day, "count": by_day.get(day, 0)})
        won, lost = by_status.get("won", 0), by_status.get("lost", 0)
        return {
            "total": total,
            "avg_score": round(avg_score or 0, 1),
            "needs_review": int(review or 0),
            "win_rate": round(won / (won + lost), 3) if won + lost else None,
            "median_latency_ms": _median(latencies),
            "by_priority": {p: by_priority.get(p, 0) for p in PRIORITIES},
            "by_status": {s: by_status.get(s, 0) for s in STATUSES},
            "daily": daily,
            "by_source": [
                {
                    "source": r["src"],
                    "count": r["n"],
                    "won": int(r["won"] or 0),
                    "closed": int(r["closed"] or 0),
                    "win_rate": round(r["won"] / r["closed"], 3) if r["closed"] else None,
                    "avg_score": round(r["avg_score"] or 0, 1),
                }
                for r in sources
            ],
        }

    def all_ids(self) -> list:
        with self._connect() as conn:
            return [row[0] for row in conn.execute("SELECT id FROM leads ORDER BY id")]

    def delete(self, lead_id: int) -> bool:
        with self._connect() as conn:
            return conn.execute("DELETE FROM leads WHERE id = ?", (lead_id,)).rowcount > 0

    def iter_csv(self) -> Iterator[str]:
        """Yields the whole inbox as CSV text, newest first."""
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=_CSV_COLUMNS)
        writer.writeheader()
        yield buffer.getvalue()

        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM leads ORDER BY id DESC").fetchall()
        for row in rows:
            contact = json.loads(row["lead_json"]).get("contact") or {}
            buffer.seek(0)
            buffer.truncate()
            writer.writerow(
                {
                    col: _csv_safe(value)
                    for col, value in {
                        "id": row["id"],
                        "received_at": row["received_at"],
                        "source": row["source"],
                        "contact_name": row["contact_name"],
                        "company_name": row["company_name"],
                        "email": contact.get("email"),
                        "phone": contact.get("phone"),
                        "total_score": row["total_score"],
                        "priority": row["priority"],
                        "status": row["status"],
                        "requires_review": bool(row["requires_review"]),
                        "engine": row["engine"],
                        "summary": row["summary"],
                        "message": row["message"],
                        "notes": row["notes"],
                    }.items()
                }
            )
            yield buffer.getvalue()
