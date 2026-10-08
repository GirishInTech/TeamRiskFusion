from datetime import datetime, timedelta
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Topic, Subtopic, Project, ProjectComponent, ProjectPerson, Attribute, Entry, Source, Document, DB_URL

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
db = SessionLocal()

def dt(y, m, d):
    return datetime(y, m, d)

# Topics
t1 = Topic(name="Credit Risk Dashboards", description="Exposure views analysts use at month-end. If a number looks off, start here — no ticket needed.")
t2 = Topic(name="Market Risk Reports", description="RWA, limits and movements. What changed, why, and whether it is real risk or a feed issue.")
t3 = Topic(name="Data & Refresh Ops", description="Feeds, cut-off times and how to request a change. The plumbing behind every dashboard.")
db.add_all([t1, t2, t3]); db.flush()

s_exp = Subtopic(topic_id=t1.id, name="Exposure Metrics")
s_use = Subtopic(topic_id=t1.id, name="Dashboard Usage")
s_rwa = Subtopic(topic_id=t2.id, name="RWA & Capital")
s_lim = Subtopic(topic_id=t2.id, name="Limit Monitoring")
s_feed = Subtopic(topic_id=t3.id, name="Feeds & Cut-offs")
s_chg = Subtopic(topic_id=t3.id, name="Change Process")
db.add_all([s_exp, s_use, s_rwa, s_lim, s_feed, s_chg]); db.flush()

# Projects
p1 = Project(name="Counterparty Exposure Dashboard", subtopic_id=s_exp.id,
             summary="Main exposure dashboard for credit risk. EAD / PFE by counterparty, netting set and desk.",
             status="live", owner_name="Marc Dubois (left Sept 2026)")
p2 = Project(name="RWA Movement Report", subtopic_id=s_rwa.id,
             summary="Monthly RWA movement explain: what moved, feed vs methodology vs real risk.",
             status="live", owner_name="Aisha Khan")
p3 = Project(name="Limit Monitoring v2", subtopic_id=s_lim.id,
             summary="New limit-breach monitor Priya will extend. Intraday checks + alert routing.",
             status="ongoing", owner_name="Jonas Weber")
p4 = Project(name="CVA Feed Migration", subtopic_id=s_feed.id,
             summary="Old CVA feed moved to the new risk feed. Deprecated — kept for lineage only.",
             status="deprecated", owner_name="Sofia Rossi")
db.add_all([p1, p2, p3, p4]); db.flush()

comps = [
    # p1: 2 APIs, 1 DB, 1 repo, 2 reports
    (p1.id, "api", "Exposure API — netting set EAD", "/api/v1/exposure/netting-set", "p95 300ms, auth via DAF gateway"),
    (p1.id, "api", "Counterparty API — PFE series", "/api/v1/counterparty/pfe", "Daily series, paginated by counterparty id"),
    (p1.id, "database", "Risk exposure store", "RISQ_EXPOSURE_DB", "EOD snapshot table T_EXPOSURE_EOD"),
    (p1.id, "repo", "Dashboard frontend + ETL", "github.com/socgen/risq-exposure-dash", "main branch, deploys Fridays"),
    (p1.id, "report", "Downstream: Monthly Exposure Pack", "Exposure Pack (PDF, month-end)", "Built from this dashboard"),
    (p1.id, "dashboard", "Counterparty Exposure Dashboard", "https://risq.internal/dash/exposure", "The dashboard itself"),
    (p1.id, "api", "Trades feed — front-office exposure", "/api/v1/trades/exposure", "Refreshed every 30 min (Arjun KT Sept 2026)"),
    (p1.id, "database", "Market data snapshot", "RISK_MKT_SNAP", "Cut-off 6pm IST daily"),
    (p1.id, "repo", "Refresh job exposure-refresh", "github.com/socgen/risq-exposure-dash — job exposure-refresh", "If fail: check feed cut-off first, re-run after 6:30pm IST"),
    (p2.id, "report", "RWA Movement Report", "https://risq.internal/reports/rwa-movement", "Monthly, published T+3"),
    (p2.id, "database", "RWA results store", "RISQ_RWA_DB", "T_RWA_MONTHLY table"),
    (p2.id, "repo", "RWA explain notebook", "github.com/socgen/risq-rwa-explain", "Mapping csv lives here"),
    (p3.id, "api", "Limit check API", "/api/v1/limits/check", "Intraday, 5-min cache"),
    (p3.id, "repo", "Limit monitor service", "github.com/socgen/risq-limits-v2", "Owner: Jonas Weber"),
    (p3.id, "database", "Limits config DB", "RISQ_LIMITS_DB", "T_LIMITS + T_BREACHES"),
    (p4.id, "database", "Legacy CVA feed", "RISQ_CVA_LEGACY", "Frozen since June 2026"),
    (p4.id, "database", "New CVA feed", "RISQ_CVA_NEW", "Cut over Aug 2026"),
    (p4.id, "doc", "Migration runbook", "Confluence: CVA migration runbook", "Steps + rollback plan"),
]
for pid, kind, label, ref, notes in comps:
    db.add(ProjectComponent(project_id=pid, kind=kind, label=label, ref=ref, notes=notes))

people = [
    (p1.id, "Marc Dubois (left Sept 2026)", "owner"),
    (p1.id, "Aisha Khan", "contributor"),
    (p1.id, "Arjun (rotating off end Sept 2026)", "contributor"),
    (p1.id, "Priya Nair", "contributor"),
    (p2.id, "Aisha Khan", "owner"),
    (p2.id, "Jonas Weber", "contributor"),
    (p3.id, "Jonas Weber", "owner"),
    (p3.id, "Priya Nair", "contributor"),
    (p4.id, "Sofia Rossi", "owner"),
]
for pid, name, role in people:
    db.add(ProjectPerson(project_id=pid, person_name=name, role=role))

db.add(Attribute(owner_type="project", owner_id=p1.id, key="refresh_cadence", value="Daily 06:30 CET, EOD snapshot"))
db.add(Attribute(owner_type="project", owner_id=p1.id, key="how_to_request_change", value="File DAF request type 'metric-change', tag owner Aisha Khan"))
db.add(Attribute(owner_type="project", owner_id=p1.id, key="jira_component", value="exposure-dash — analysts raise Jira tagged exposure-dash, lands in team queue (Arjun KT)"))
db.add(Attribute(owner_type="project", owner_id=p3.id, key="how_to_extend", value="Add rule in limits-service/rules.yaml, add test, ping Jonas Weber for review"))
db.flush()

# Entries (~15). verified_at staggered; one STALE via repo source newer.
def add_entry(sub_id, proj_id, title, body, kind, author, verified, sources):
    e = Entry(subtopic_id=sub_id, project_id=proj_id, title=title, body=body,
              entry_kind=kind, author=author, created_at=verified, verified_at=verified)
    db.add(e); db.flush()
    for stype, sref, supd in sources:
        db.add(Source(entry_id=e.id, source_type=stype, source_ref=sref, source_updated_at=supd))
    return e

add_entry(s_exp.id, p1.id, "What is EAD? (plain language)",
          "EAD = Exposure at Default: how much we would lose if the counterparty defaulted tomorrow, after netting and collateral.\n\nUse it for: month-end exposure packs.\nDo NOT use it for: intraday trading decisions (it is an EOD snapshot).",
          "definition", "Marc Dubois", dt(2026, 5, 10), [("manual", "exposure-dash README", dt(2026, 5, 10))])
add_entry(s_exp.id, p1.id, "What is PFE?",
          "PFE = Potential Future Exposure: worst-case exposure at 95% confidence over the margin period.\n\nHigh PFE + low EAD = risky directionally. Check the netting-set view before escalating.",
          "definition", "Aisha Khan", dt(2026, 6, 2), [("manual", "exposure-dash README", dt(2026, 6, 2))])
add_entry(s_use.id, p1.id, "Number looks off at month-end? Read this first",
          "1. Check refresh banner: data is EOD, refreshed 06:30 CET.\n2. Check caveats list for known feed issues.\n3. Compare vs last month in the Movement tab.\n\nIf still off, request a change (see Change Process) — no ticket queue needed.",
          "howto", "Aisha Khan", dt(2026, 7, 15), [("manual", "analyst-runbook", dt(2026, 7, 15))])
add_entry(s_use.id, p1.id, "Refresh cadence + cut-off times",
          "Dashboard refreshes daily at 06:30 CET from the EOD snapshot.\nCut-off: trades booked after 19:00 CET appear next day.\nMonth-end pack freezes on T+2.",
          "howto", "Marc Dubois", dt(2026, 6, 20), [("manual", "ops-calendar", dt(2026, 6, 20))])
add_entry(s_use.id, p1.id, "Owner left — who do I talk to now?",
          "Built by Marc Dubois (left Sept 2026). Owned now by Aisha Khan.\nHow to extend: repo link on the project page + runbook. Continuity card has the full handover.",
          "note", "Aisha Khan", dt(2026, 9, 20), [("manual", "handover-note", dt(2026, 9, 20))])
add_entry(s_rwa.id, p2.id, "March RWA jump was a feed mapping issue, not real risk",
          "In March 2026 RWA jumped +€1.2bn. Cause: legacy CVA feed mapped 'cleared' trades as 'bilateral'.\nFixed in April mapping csv (see repo). Do not cite March as a risk increase in decks.",
          "caveat", "Aisha Khan", dt(2026, 4, 12), [("jira", "RISQ-4821 feed-mapping", dt(2026, 4, 12))])
add_entry(s_rwa.id, p2.id, "What is RWA movement explain?",
          "RWA moves for 3 reasons: (1) real risk (positions), (2) feed/mapping changes, (3) methodology.\nThe report splits all three. Always quote the split, never the headline number alone.",
          "definition", "Aisha Khan", dt(2026, 5, 5), [("manual", "rwa-methodology-v3", dt(2026, 5, 5))])
# STALE entry: verified Jan, repo updated Mar
add_entry(s_rwa.id, p2.id, "RWA mapping csv location (STALE demo)",
          "Mapping lives in the rwa-explain repo, file mapping/march.csv.\n(In demo this entry is STALE because the repo updated after verification.)",
          "note", "Jonas Weber", dt(2026, 1, 15), [("repo", "github.com/socgen/risq-rwa-explain", dt(2026, 3, 2))])
add_entry(s_lim.id, p3.id, "How limit breaches are computed",
          "Breach = exposure > limit for 2 consecutive 5-min checks (avoids flicker).\nAlerts route to desk + risk owner via email/Symphony mock.",
          "definition", "Jonas Weber", dt(2026, 8, 1), [("manual", "limits-v2-spec", dt(2026, 8, 1))])
add_entry(s_lim.id, p3.id, "Priya start here: where do I get the data?",
          "Use Limit Monitoring v2 project page: APIs, DB names and repo are listed in the components table.\nDB: RISQ_LIMITS_DB. API: /api/v1/limits/check. Owner to talk to: Jonas Weber.\nNo need to ask around for 2 weeks.",
          "howto", "Jonas Weber", dt(2026, 9, 1), [("kt_transcript", "KT Jonas->Priya 28-Aug", dt(2026, 9, 1))])
add_entry(s_feed.id, p4.id, "CVA feed cut-over: what changed",
          "Legacy RISQ_CVA_LEGACY frozen June 2026. New feed RISQ_CVA_NEW live since Aug 2026.\nAll dashboards should point to the new feed. Legacy kept for audit only.",
          "caveat", "Sofia Rossi", dt(2026, 8, 15), [("manual", "migration-runbook", dt(2026, 8, 15))])
# Topic 3 single-contributor: all by Sofia Rossi
add_entry(s_feed.id, None, "Feed cut-off times",
          "All risk feeds cut off at 19:00 CET. Late trades roll to next EOD.\nCVA new feed publishes by 22:00 CET.",
          "howto", "Sofia Rossi", dt(2026, 7, 1), [("manual", "ops-calendar", dt(2026, 7, 1))])
add_entry(s_chg.id, None, "How to request a change (process)",
          "1. Open DAF request type 'metric-change' or 'new-slice'.\n2. Tag current owner (see project page).\n3. Owner verifies + updates the knowledge entry — the entry stays fresh automatically.\nSLA: 3 business days for acknowledgement.",
          "process", "Sofia Rossi", dt(2026, 7, 10), [("manual", "daf-playbook", dt(2026, 7, 10))])
add_entry(s_chg.id, p1.id, "Dashboard access for new joiners",
          "Access via DAF group 'risq-analyst'. Takes ~1 day.\nPriya got access in 2 minutes of reading this page instead of asking around.",
          "process", "Sofia Rossi", dt(2026, 8, 20), [("manual", "access-guide", dt(2026, 8, 20))])
add_entry(s_exp.id, p1.id, "Netting sets explained in one paragraph",
          "A netting set = trades with one counterparty under one master agreement that can be netted.\nExposure is computed per netting set, then summed. If one trade looks huge, check its netting set first.",
          "definition", "Marc Dubois", dt(2026, 5, 22), [("kt_transcript", "KT Marc 12-May", dt(2026, 5, 22))])
# Arjun -> Priya KT handover (Sept 2026) — Counterparty Exposure Dashboard
add_entry(s_exp.id, p1.id, "PFE in business terms",
          "PFE = Potential Future Exposure: the worst-case loss we'd face if the counterparty defaults at the worst possible moment.\nIt moves mainly with market volatility and trade maturity.",
          "definition", "Arjun", dt(2026, 9, 28), [("kt_transcript", "KT Arjun->Priya Counterparty Exposure handover", dt(2026, 9, 28))])
add_entry(s_exp.id, p1.id, "Exposure data sources: trades feed + market snapshot",
          "Two feeds:\n1. Trades feed from front-office API, endpoint /api/v1/trades/exposure, refreshed every 30 minutes.\n2. Market data snapshot from RISK_MKT_SNAP database table, cut-off 6pm IST daily.",
          "howto", "Arjun", dt(2026, 9, 28), [("kt_transcript", "KT Arjun->Priya Counterparty Exposure handover", dt(2026, 9, 28))])
add_entry(s_exp.id, p1.id, "March spike was a feed mapping issue, not real risk",
          "RWA jumped 40% in March and everyone panicked, but it was a feed mapping issue on our side, not real risk.\nAlways check the caveat entries before raising an alarm.",
          "caveat", "Arjun", dt(2026, 9, 28), [("kt_transcript", "KT Arjun->Priya Counterparty Exposure handover", dt(2026, 9, 28))])
add_entry(s_use.id, p1.id, "Dashboard not refreshing? Check this first",
          "The refresh job is `exposure-refresh` in the repo.\nIf it fails, check the feed cut-off first — 90% of the time the market data snapshot just arrived late.\nRe-running after 6:30pm IST fixes it.",
          "howto", "Arjun", dt(2026, 9, 28), [("kt_transcript", "KT Arjun->Priya Counterparty Exposure handover", dt(2026, 9, 28))])
add_entry(s_use.id, p1.id, "Exposure ownership + how analysts request changes",
          "Owner: Arjun until end of September, then Priya.\nAnalysts raise a Jira ticket tagged with component `exposure-dash` and it lands in the team queue.",
          "process", "Arjun", dt(2026, 9, 28), [("kt_transcript", "KT Arjun->Priya Counterparty Exposure handover", dt(2026, 9, 28))])

# One seeded example document on the Counterparty Exposure project (file on disk).
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
seed_filename = "exposure-feed-mapping.csv"
seed_stored = f"seed_{seed_filename}"
with open(os.path.join(UPLOAD_DIR, seed_stored), "w") as f:
    f.write("counterparty,netting_set,trade_type,feed_code,mapped_type,note\n"
            "ACME Corp,NS-101,cleared,CLR,bilateral,MARCH FIX: was mapped bilateral — corrected April\n"
            "Globex,NS-204,bilateral,BIL,bilateral,ok\n"
            "Initech,NS-318,cleared,CLR,cleared,ok post April mapping\n")
seed_doc = Document(project_id=p1.id, entry_id=None, filename=seed_filename,
                    stored_name=seed_stored, content_type="text/csv",
                    size_bytes=os.path.getsize(os.path.join(UPLOAD_DIR, seed_stored)),
                    uploaded_by="Arjun", created_at=dt(2026, 9, 28))
db.add(seed_doc)

db.commit()
print(f"Seeded: topics={db.query(Topic).count()} projects={db.query(Project).count()} entries={db.query(Entry).count()} documents={db.query(Document).count()}")
