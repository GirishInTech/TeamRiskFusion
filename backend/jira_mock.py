"""Deterministic mock-Jira backend (demo only — no network calls).

Given any ticket key, derive a stable ticket (summary, description, labels,
reporter, consecutive worklogs) from a SHA-256 hash. Same key always yields
the same ticket, on any machine, offline. All content is fictional.
"""
import hashlib
from datetime import datetime, timedelta

BASE_UPDATED = datetime(2026, 9, 20)

SUMMARIES = [
    "EEPE mismatch between mart and iFlow display",
    "Mart refresh delayed past cut-off",
    "Widget shows stale cut-off after re-run",
    "LR pack does not foot to SA-CCR EAD",
]

DESCRIPTIONS = [
    "Analysts report the EEPE figure on iFlow does not match the mart column for the same netting set. "
    "Suspected cause: display cache, not the engine. All figures here are illustrative patterns, never real data.",
    "The nightly mart build finished after the 6pm IST cut-off, so iFlow, LR and widgets all showed "
    "the previous snapshot. Re-running after the late snapshot resolved it.",
    "After a manual re-run, one widget kept the previous cut-off label while showing fresh numbers. "
    "Suspected cause: widget-level caching of the cut-off string.",
    "Month-end LR exposure does not reconcile to SA-CCR EAD. First check whether the EEPE engine "
    "moved before opening a methodology debate. Tolerance figures here are illustrative.",
]

LABELS_POOL = ["ccr-iflow", "eepe-engine", "mart", "lr-pack", "month-end",
               "cutoff", "mapping", "widget"]

WORKLOG_TEXTS = [
    "Reproduced on the previous snapshot; engine output matches the mart, so the engine is clear.",
    "Checked the cut-off timestamps — snapshot landed late, displays rolled forward after re-run.",
    "Compared widget query against the EEPE endpoint directly; numbers agree, only the label lagged.",
    "Confirmed mart column and iFlow report read the same netting-set key; no mapping drift.",
    "Re-ran the pack after the late snapshot; figures reconciled within the illustrative tolerance.",
    "Left a note for the next month-end: check feed cut-off before doubting the engine.",
]

WORKLOG_AUTHORS = ["Kiran Nair", "Likhitha Sharma", "Nikhil Patel", "Girish Menon"]
REPORTERS = ["Likhitha Sharma", "Girish Menon", "Nikhil Patel"]


def mock_jira_ticket(key: str) -> dict:
    """Return a stable mock ticket for any key. Datetimes, not strings."""
    key = (key or "").strip().upper()
    if not key:
        raise ValueError("empty ticket key")
    h = int(hashlib.sha256(key.encode()).hexdigest(), 16)
    state = h

    def rnd(n: int) -> int:
        nonlocal state
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        return state % n

    summary = SUMMARIES[rnd(len(SUMMARIES))]
    description = DESCRIPTIONS[rnd(len(DESCRIPTIONS))]
    labels = sorted({LABELS_POOL[rnd(len(LABELS_POOL))] for _ in range(3)})[:3] or [LABELS_POOL[0]]
    reporter = REPORTERS[rnd(len(REPORTERS))]
    nlogs = 2 + rnd(3)  # 2-4 consecutive worklogs
    worklogs = []
    for _ in range(nlogs):
        created = BASE_UPDATED - timedelta(days=rnd(10), hours=rnd(8), minutes=rnd(50))
        worklogs.append({"author": WORKLOG_AUTHORS[rnd(len(WORKLOG_AUTHORS))],
                         "created": created,
                         "text": WORKLOG_TEXTS[rnd(len(WORKLOG_TEXTS))]})
    worklogs.sort(key=lambda w: w["created"])  # consecutive, oldest first
    updated = max([w["created"] for w in worklogs]) + timedelta(hours=1)
    return {"ticket_key": key, "summary": summary, "description": description,
            "labels": labels, "reporter": reporter, "worklogs": worklogs,
            "updated_at": updated}


def ticket_payload(t: dict) -> dict:
    """JSON-safe version of a mock ticket."""
    return {**t, "updated_at": t["updated_at"].isoformat(),
            "worklogs": [{**w, "created": w["created"].isoformat()} for w in t["worklogs"]]}
