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

## 3-minute demo script (CCR workflow)
- 0:00–0:25 Analyst pain: morning CVaR number looks off, iFlow author (Manoj Iyer) left Sept 2026. Before = file ticket and wait.
- 0:25–1:10 Knowledge page: Analyst home → "CVAR & Counterparty Risk" → March-spike caveat (mapping issue, not real risk) + CVaR/EEPE definitions, refresh cadence, owner, how to request change. No ticket.
- 1:10–1:50 New dev Likhitha on CVAR Adjustment iFlow: Dev Projects → project page shows the codebase (serves iFlow + widgets), the shared EEPE engine, endpoint, mart, owner Kiran Nair → "Likhitha start here" entry → Related via shared pieces (no codebase digging).
- 1:50–2:20 Effortless capture: Knowledge Feed tab → Log a project (only 5 required fields) or paste KT transcript → deterministic drafts → Approve creates everything. Plus Import Jira (type ticket IDs → preview description/labels/worklogs → import to the project).
- 2:20–2:50 Continuity + impact: CCR Data Creator page → Downstream impact panel (EEPE engine also feeds iFlow, LR, widgets — "what breaks if this changes") + health panel (red single-owner warning, stale list) + continuity card. STALE demo entries: "SA-CCR mapping csv location" + "EEPE endpoint pagination changed" (dev view).
- 2:50–3:00 Punchline: analysts get answers, developers find everything, nothing becomes an orphan.

## Scope
In scope: project registry (manual 5-field form or unstructured-document import → AI-structured editable draft) + KT transcript → drafts + mock Jira import (ticket IDs → description + labels + consecutive worklogs, single or multi-ticket) + repo-grounded chat (deterministic retrieval over entries/projects/components, no LLM) + repo attach + document attach, topic browsing, entries linked to projects, discovery incl. shared-piece related + downstream impact, requirement docs + requirement-sourced entries, health panel, stale flags.
Out of scope (roadmap): emails, DB-as-source, real AppStudio/SG Dashboard links, auth, real Jira/GitHub, chatbot, full-text search (simple filter only).

## Data rule
Fixed core columns for what matters, everything else as ROWS: `project_components` (api/database/repo/dashboard/widget/computation/report/doc/...) + `attributes` key-value escape hatch. Sharing = byte-identical `ref` (same codebase/endpoint/computation/database); related + lineage compute on read, stored nowhere. Staleness: STALE if any source `source_updated_at > entry.verified_at`.

## Seed data note (fictional)
Real team project names (CVAR Adjustment iFlow, CCR Data Creator, LR Accuracy) anchor the demo; everything marked (illustrative) is invented. All figures in seed content are fictional patterns, never real data.
