"""
Synthetic incident / ticket data for resume demos (no external API).
Loaded from data/synthetic_incidents.json (edit that file to add more rows).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _data_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "data" / "synthetic_incidents.json"


def _load_incidents() -> list[dict[str, Any]]:
    path = _data_path()
    if not path.exists():
        logger.warning("Missing incident catalog at %s — tool will return no data", path)
        return []
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, list):
        return []
    return sorted(raw, key=lambda x: str(x.get("updated_at", "")), reverse=True)


MOCK_INCIDENTS: list[dict[str, Any]] = _load_incidents()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def lookup_ticket(ticket_id: str) -> dict[str, Any]:
    tid = ticket_id.strip().upper()
    for inc in MOCK_INCIDENTS:
        if str(inc.get("ticket_id", "")).upper() == tid:
            return {
                "found": True,
                "op": "get_incident",
                "source": "synthetic_itsm_snapshot",
                "incident": dict(inc),
            }
    return {
        "found": False,
        "op": "get_incident",
        "ticket_id": ticket_id,
        "source": "synthetic_itsm_snapshot",
        "checked_at": _now_iso(),
    }


def list_incidents(
    *,
    status: str | None = None,
    limit: int = 15,
) -> dict[str, Any]:
    rows = list(MOCK_INCIDENTS)
    if status:
        st = status.lower()
        rows = [i for i in rows if str(i.get("status", "")).lower() == st]
    cap = max(1, min(limit, 100))
    rows = rows[:cap]
    return {
        "found": True,
        "op": "list_incidents",
        "source": "synthetic_itsm_snapshot",
        "filter_status": status,
        "count": len(rows),
        "incidents": [dict(i) for i in rows],
    }


def search_incidents(query: str, *, limit: int = 10) -> dict[str, Any]:
    q = (query or "").lower().strip()
    if not q:
        return {
            "found": True,
            "op": "search_incidents",
            "source": "synthetic_itsm_snapshot",
            "query": query,
            "count": 0,
            "incidents": [],
        }
    keys = ("ticket_id", "title", "service", "category", "assignee_team", "summary")
    hits: list[dict[str, Any]] = []
    for inc in MOCK_INCIDENTS:
        parts = [str(inc.get(k, "")) for k in keys]
        tags = inc.get("tags")
        if isinstance(tags, list):
            parts.append(" ".join(str(t) for t in tags))
        hay = " ".join(parts).lower()
        if q in hay:
            hits.append(dict(inc))
        if len(hits) >= limit:
            break
    return {
        "found": True,
        "op": "search_incidents",
        "source": "synthetic_itsm_snapshot",
        "query": query,
        "count": len(hits),
        "incidents": hits,
    }
