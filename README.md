# TeamRiskFusion — Knowledge Repository (SocGen Hackathon Demo)

Capturing expertise is a byproduct of work people already do — not a wiki that waits for docs.
Analysts get answers without tickets, developers log once / discover everything, business keeps continuity when people leave.

> Wikis wait for people to write. Ours extracts.

## Run (no Docker, offline-safe, no LLM calls)

Backend (FastAPI + SQLite):
```
cd backend
pip install -r requirements.txt
python seed.py
uvicorn app:app --reload --port 8000
```

Frontend (React + Vite):
```
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. API at http://localhost:8000.

## 3-minute demo script
- 0:00–0:25 Analyst pain: month-end number off, dashboard author (Marc Dubois) left Sept 2026. Before = file ticket and wait.
- 0:25–1:10 Knowledge page: Analyst home → "Credit Risk Dashboards" → entry "Number looks off? Read this first" + EAD/PFE definitions, refresh cadence, owner, how to request change. No ticket.
- 1:10–1:50 New dev Priya: Dev Projects → filter "limit" → "Limit Monitoring v2" → databases, `/api/v1/limits/check`, repo, owner Jonas Weber + "Priya start here" entry.
- 1:50–2:20 Effortless capture: Capture tab → Log a project (only 5 required fields) or paste KT transcript → deterministic drafts → Approve creates everything. Plus Import Jira (paste mock JSON).
- 2:20–2:50 Continuity: Topic health panel (contributors, freshness %, red single-owner warning, stale list) + per-project card: built by / made of / owned now by / how to extend. STALE demo entry: "RWA mapping csv location".
- 2:50–3:00 Punchline: analysts get answers, developers find everything, nothing becomes an orphan.

## Scope
In scope: project registry + KT transcript → drafts + mocked Jira import + repo attach, topic browsing, entries linked to projects, discovery, health panel, stale flags.
Out of scope (roadmap): emails, DB-as-source, files, APIs, DAF endpoints, auth, real Jira/GitHub, chatbot, full-text search (simple filter only).

## Data rule
Fixed core columns for what matters, everything else as ROWS: `project_components` (api/database/repo/dashboard/report/...) + `attributes` (key-value escape hatch). Staleness computed on read: STALE if any source `source_updated_at > entry.verified_at`.
