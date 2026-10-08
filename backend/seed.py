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

# ---------------------------------------------------------------------------
# CCR domain seed. Real team project names are used as-is; anything invented
# is marked (illustrative) in its label/summary/body. All figures below are
# fictional patterns, never real data.
# Sharing rule (lineage backbone): projects that reuse the same computation,
# endpoint, database or codebase use the BYTE-IDENTICAL ref string defined
# here, so "related" and "downstream impact" compute from shared refs.
# ---------------------------------------------------------------------------
CODEBASE = "github.com/socgen/ccr-risk-apps"
EEPE_ENGINE = "eepe-engine-saccr-v2"
EEPE_API = "/api/ccr/exposure/eepe"
MART = "CCR_RISK_MART"
LR_API = "/api/lr/saccr-inputs"

# Topics
t1 = Topic(name="CVAR & Counterparty Risk", description="CVaR views CCR users open every morning. If a number looks off, start here — no ticket needed.")
t2 = Topic(name="SA-CCR & Leverage Ratio", description="Shared SA-CCR computations (PFE/EEPE/EAD) and how they feed the leverage ratio.")
t3 = Topic(name="Feeds, Requirements & Change", description="Feeds, user requirement files and how to request a change. The paper trail behind every widget.")
t4 = Topic(name="SGMR", description="Reconciliations and consolidations the desk signs off. Breaks, RA packs and month-end sign-off live here.")
db.add_all([t1, t2, t3, t4]); db.flush()

s_cvar = Subtopic(topic_id=t1.id, name="CVAR & Exposure Views")
s_app = Subtopic(topic_id=t1.id, name="AppStudio Reports")
s_comp = Subtopic(topic_id=t2.id, name="Shared Computations")
s_lr = Subtopic(topic_id=t2.id, name="Leverage Ratio")
s_feed = Subtopic(topic_id=t3.id, name="Feeds & Cut-offs")
s_chg = Subtopic(topic_id=t3.id, name="Change Process")
s_rec = Subtopic(topic_id=t4.id, name="Reconciliation Reports")
s_sgpack = Subtopic(topic_id=t4.id, name="Consolidation & Sign-off Packs")
db.add_all([s_cvar, s_app, s_comp, s_lr, s_feed, s_chg, s_rec, s_sgpack]); db.flush()

# Projects (3 real names + 2 clearly-marked illustrative ones)
p1 = Project(name="CVAR Adjustment iFlow", subtopic_id=s_cvar.id,
             summary="AppStudio website carrying the CVaR reports CCR users check daily. Served by the shared ccr-risk-apps codebase; consumes the shared EEPE engine.",
             status="live", owner_name="Manoj Iyer (left Sept 2026)")
p2 = Project(name="CCR Data Creator", subtopic_id=s_comp.id,
             summary="Builds the shared CCR datasets and computations (EEPE engine, exposure mart) that iFlow, LR Accuracy and the widget pack all consume.",
             status="ongoing", owner_name="Kiran Nair")
p3 = Project(name="LR Accuracy", subtopic_id=s_lr.id,
             summary="Leverage-ratio pack whose exposure inputs come from SA-CCR EAD. If SA-CCR moves, LR moves.",
             status="live", owner_name="Girish Menon")
p4 = Project(name="PFE Widget Pack (illustrative)", subtopic_id=s_cvar.id,
             summary="ILLUSTRATIVE example: SG Dashboard widgets for PFE by netting set, served by the same codebase as CVAR iFlow.",
             status="ongoing", owner_name="Likhitha Sharma")
p5 = Project(name="SA-CCR Feed Archive (illustrative)", subtopic_id=s_feed.id,
             summary="ILLUSTRATIVE example: frozen legacy SA-CCR feed, kept for lineage only.",
             status="deprecated", owner_name="Divya Reddy")
# SGMR reports (2 team names + 2 clearly-marked illustrative ones)
p6 = Project(name="SGMR Data Reconciliation", subtopic_id=s_rec.id,
             summary="Nightly recon between front-office feeds and the risk mart. A break here blocks sign-off.",
             status="live", owner_name="Girish Menon")
p7 = Project(name="Global RA Consolidation", subtopic_id=s_sgpack.id,
             summary="Aggregates regional RA packs into one global view. Runs on the RA consolidator codebase.",
             status="ongoing", owner_name="Likhitha Sharma")
p8 = Project(name="SGMR P&L Explain Pack (illustrative)", subtopic_id=s_rec.id,
             summary="ILLUSTRATIVE example: daily P&L explain built off the recon engine outputs.",
             status="live", owner_name="Nikhil Patel")
p9 = Project(name="SGMR Month-End Sign-off Pack (illustrative)", subtopic_id=s_sgpack.id,
             summary="ILLUSTRATIVE example: month-end sign-off pack assembled from the RA consolidation.",
             status="live", owner_name="Divya Reddy")
db.add_all([p1, p2, p3, p4, p5, p6, p7, p8, p9]); db.flush()

# SGMR codebases (shared refs: reports run on how these are built)
CB_REC = "github.com/socgen/sgmr-recon-engine"
CB_RA = "github.com/socgen/sgmr-ra-consolidator"
CB_APPS = "github.com/socgen/sgmr-reporting-apps"

comps = [
    # p1 CVAR Adjustment iFlow
    (p1.id, "repo", "Codebase ccr-risk-apps (serves iFlow + widgets)", CODEBASE, "One codebase, multiple reports/dashboards"),
    (p1.id, "computation", "EEPE engine (SA-CCR)", EEPE_ENGINE, "Owned by CCR Data Creator; consumed here"),
    (p1.id, "api", "EEPE by netting set", EEPE_API, "Refreshed every 30 min (Nikhil Patel KT Sept 2026)"),
    (p1.id, "database", "Exposure mart", MART, "Netting-set EEPE table T_EEPE_NETTING (illustrative schema)"),
    (p1.id, "report", "AppStudio: CVAR Adjustment Reports", "appstudio://cvar-adjustment-reports", "The user-facing reports"),
    (p1.id, "doc", "User requirement REQ-CVAR-014", "REQ-CVAR-014-user-requirements.md", "Attached under Documents"),
    # p2 CCR Data Creator (the upstream everything depends on)
    (p2.id, "computation", "EEPE engine (SA-CCR)", EEPE_ENGINE, "Single implementation shared by iFlow, LR, widgets"),
    (p2.id, "api", "EEPE by netting set", EEPE_API, "Published here, consumed downstream"),
    (p2.id, "api", "SA-CCR inputs for LR", LR_API, "Feeds LR Accuracy"),
    (p2.id, "database", "Exposure mart", MART, "Written here, read downstream"),
    (p2.id, "repo", "Data pipelines", "github.com/socgen/ccr-data-pipelines", "Nightly build + checks"),
    (p2.id, "doc", "User requirement REQ-CCR-DATA-007", "REQ-CCR-DATA-007-mart-requirements.md", "Attached under Documents"),
    # p3 LR Accuracy
    (p3.id, "computation", "EEPE engine (SA-CCR)", EEPE_ENGINE, "EAD out of this engine feeds LR exposure"),
    (p3.id, "database", "Exposure mart", MART, "Reads netting-set EAD"),
    (p3.id, "api", "SA-CCR inputs for LR", LR_API, "Consumed from CCR Data Creator"),
    (p3.id, "report", "AppStudio: LR pack", "appstudio://lr-accuracy-pack", "Monthly LR reconciliation (illustrative)"),
    (p3.id, "doc", "User requirement REQ-LR-003", "REQ-LR-003-leverage-requirements.md", "Attached under Documents"),
    # p4 PFE Widget Pack (illustrative)
    (p4.id, "repo", "Codebase ccr-risk-apps (serves iFlow + widgets)", CODEBASE, "Same codebase as CVAR iFlow — fix once, fix both"),
    (p4.id, "api", "EEPE by netting set", EEPE_API, "Same endpoint as iFlow"),
    (p4.id, "dashboard", "SG Dashboard: CCR Overview", "sg-dash://ccr-overview", "Host dashboard (illustrative)"),
    (p4.id, "widget", "Widget: PFE by netting set", "sg-dash://ccr-overview/widget-pfe-netting", "Illustrative widget"),
    (p4.id, "widget", "Widget: EEPE trend", "sg-dash://ccr-overview/widget-eepe-trend", "Illustrative widget"),
    # p5 archive (illustrative)
    (p5.id, "database", "Legacy SA-CCR feed", "CCR_SACCR_LEGACY (illustrative)", "Frozen June 2026 (illustrative)"),
    (p5.id, "doc", "Archive runbook", "Confluence: SA-CCR archive runbook (illustrative)", "Steps + rollback plan"),
    # p6 SGMR Data Reconciliation
    (p6.id, "repo", "Recon engine (serves recon + P&L explain)", CB_REC, "Reports run on how this codebase is built"),
    (p6.id, "repo", "Serving layer (serves all SGMR reports)", CB_APPS, "Shared serving layer"),
    (p6.id, "database", "Recon mart", "SGMR_RECON_MART (illustrative schema)", "Breaks table T_RECON_BREAKS"),
    (p6.id, "api", "Recon breaks feed", "/api/sgmr/recon/breaks", "Nightly 04:00 CET build (illustrative schedule)"),
    (p6.id, "report", "AppStudio: SGMR Data Reconciliation", "appstudio://sgmr-data-reconciliation", "The user-facing report"),
    # p7 Global RA Consolidation
    (p7.id, "repo", "RA consolidator (serves RA + sign-off)", CB_RA, "Reports run on how this codebase is built"),
    (p7.id, "repo", "Serving layer (serves all SGMR reports)", CB_APPS, "Shared serving layer"),
    (p7.id, "database", "RA mart", "SGMR_RA_MART (illustrative schema)", "Regional packs table"),
    (p7.id, "api", "Consolidated RA feed", "/api/sgmr/ra/consolidated", "Consumed by the sign-off pack"),
    (p7.id, "report", "AppStudio: Global RA Consolidation", "appstudio://global-ra-consolidation", "The user-facing report"),
    # p8 P&L Explain Pack (illustrative)
    (p8.id, "repo", "Recon engine (serves recon + P&L explain)", CB_REC, "Same codebase as Data Reconciliation"),
    (p8.id, "repo", "Serving layer (serves all SGMR reports)", CB_APPS, "Shared serving layer"),
    (p8.id, "api", "Recon breaks feed", "/api/sgmr/recon/breaks", "Same feed as Data Reconciliation"),
    (p8.id, "report", "AppStudio: P&L Explain (illustrative)", "appstudio://sgmr-pnl-explain", "Illustrative report"),
    # p9 Sign-off Pack (illustrative)
    (p9.id, "repo", "RA consolidator (serves RA + sign-off)", CB_RA, "Same codebase as RA Consolidation"),
    (p9.id, "repo", "Serving layer (serves all SGMR reports)", CB_APPS, "Shared serving layer"),
    (p9.id, "api", "Consolidated RA feed", "/api/sgmr/ra/consolidated", "Same feed as RA Consolidation"),
    (p9.id, "report", "AppStudio: Sign-off Pack (illustrative)", "appstudio://sgmr-signoff-pack", "Illustrative report"),
]
for pid, kind, label, ref, notes in comps:
    db.add(ProjectComponent(project_id=pid, kind=kind, label=label, ref=ref, notes=notes))

people = [
    (p1.id, "Manoj Iyer (left Sept 2026)", "owner"),
    (p1.id, "Girish Menon", "contributor"),
    (p1.id, "Nikhil Patel (rotating off end Sept 2026)", "contributor"),
    (p1.id, "Likhitha Sharma", "contributor"),
    (p2.id, "Kiran Nair", "owner"),
    (p2.id, "Likhitha Sharma", "contributor"),
    (p3.id, "Girish Menon", "owner"),
    (p3.id, "Kiran Nair", "contributor"),
    (p4.id, "Likhitha Sharma", "owner"),
    (p4.id, "Kiran Nair", "contributor"),
    (p5.id, "Divya Reddy", "owner"),
    (p6.id, "Girish Menon", "owner"),
    (p6.id, "Kiran Nair", "contributor"),
    (p7.id, "Likhitha Sharma", "owner"),
    (p7.id, "Girish Menon", "contributor"),
    (p8.id, "Nikhil Patel", "owner"),
    (p8.id, "Likhitha Sharma", "contributor"),
    (p9.id, "Divya Reddy", "owner"),
    (p9.id, "Likhitha Sharma", "contributor"),
]
for pid, name, role in people:
    db.add(ProjectPerson(project_id=pid, person_name=name, role=role))

db.add(Attribute(owner_type="project", owner_id=p1.id, key="refresh_cadence", value="Daily 06:30 CET, EOD snapshot"))
db.add(Attribute(owner_type="project", owner_id=p1.id, key="jira_component", value="ccr-iflow — analysts raise Jira tagged ccr-iflow, lands in team queue (Nikhil Patel KT)"))
db.add(Attribute(owner_type="project", owner_id=p2.id, key="how_to_extend", value="Add the computation step in ccr-data-pipelines, backfill mart, ping Kiran Nair for review"))
db.add(Attribute(owner_type="project", owner_id=p6.id, key="jira_component", value="sgmr-recon — analysts raise Jira tagged sgmr-recon, lands in team queue"))
db.add(Attribute(owner_type="project", owner_id=p7.id, key="how_to_extend", value="New region? Add its RA pack mapping in the consolidator config, ping Likhitha Sharma"))
db.flush()

def add_entry(sub_id, proj_id, title, body, kind, author, verified, sources):
    e = Entry(subtopic_id=sub_id, project_id=proj_id, title=title, body=body,
              entry_kind=kind, author=author, created_at=verified, verified_at=verified)
    db.add(e); db.flush()
    for stype, sref, supd in sources:
        db.add(Source(entry_id=e.id, source_type=stype, source_ref=sref, source_updated_at=supd))
    return e

KT = "KT Nikhil Patel->Likhitha CVAR iFlow handover"

# --- CVAR & Exposure Views (p1 + p4) ---
add_entry(s_cvar.id, p1.id, "What is CVaR? (plain language)",
          "CVaR = Conditional Value-at-Risk: the average loss in the worst tail beyond VaR — 'when things go bad, how bad on average?'\n\nUse it for: daily CVaR explain packs.\nDo NOT use a single-day jump for conclusions — check the caveats first.",
          "definition", "Manoj Iyer", dt(2026, 5, 10), [("manual", "iflow README", dt(2026, 5, 10))])
add_entry(s_cvar.id, p1.id, "EEPE feeds the CVaR tail",
          "EEPE = Effective Expected Positive Exposure under SA-CCR: the time-averaged exposure behind EAD.\nChain to remember: trades + collateral → exposure paths → loss tail → CVaR. If EEPE is flat, the tail — and CVaR — barely moves.",
          "definition", "Girish Menon", dt(2026, 6, 2), [("manual", "iflow README", dt(2026, 6, 2))])
add_entry(s_cvar.id, p1.id, "PFE vs EEPE vs EAD under SA-CCR",
          "PFE = worst-case exposure at a future date. EEPE = average of expected exposures (floored, time-weighted). EAD = alpha × EEPE.\nIf PFE spikes but EEPE is flat, CVaR barely moves — check EEPE before escalating.",
          "definition", "Girish Menon", dt(2026, 6, 20), [("manual", "saccr-primer", dt(2026, 6, 20))])
add_entry(s_cvar.id, p1.id, "March spike was a feed mapping issue, not real risk (illustrative)",
          "In March, CVaR jumped sharply (illustrative figures — pattern, not real data) and everyone panicked, but it was a feed mapping issue on our side, not real risk.\nAlways check the caveat entries before raising an alarm.",
          "caveat", "Nikhil Patel", dt(2026, 9, 28), [("kt_transcript", KT, dt(2026, 9, 28))])
add_entry(s_cvar.id, p1.id, "CVAR iFlow data sources: trades feed + market snapshot",
          "Two feeds:\n1. Trades feed from front-office API, endpoint /api/ccr/exposure/eepe, refreshed every 30 minutes.\n2. Market data snapshot feeding the mart, cut-off 6pm IST daily.",
          "howto", "Nikhil Patel", dt(2026, 9, 28), [("kt_transcript", KT, dt(2026, 9, 28))])
add_entry(s_cvar.id, p1.id, "iFlow not refreshing? Check this first",
          "The refresh job is `iflow-refresh` in ccr-risk-apps.\nIf it fails, check the feed cut-off first — 90% of the time the market snapshot just arrived late.\nRe-running after 6:30pm IST fixes it.",
          "howto", "Nikhil Patel", dt(2026, 9, 28), [("kt_transcript", KT, dt(2026, 9, 28))])
add_entry(s_cvar.id, p1.id, "CVAR ownership + how users request changes",
          "Owner: Nikhil Patel until end of September, then Likhitha.\nUsers raise a Jira ticket tagged with component `ccr-iflow` and it lands in the team queue.",
          "process", "Nikhil Patel", dt(2026, 9, 28), [("kt_transcript", KT, dt(2026, 9, 28))])
add_entry(s_cvar.id, p1.id, "REQ-CVAR-014: CVaR must split by netting set",
          "From user requirement REQ-CVAR-014 (attached under Documents): the CVaR report must break the tail measure down by netting set with collateral applied.\nBuilt as: mart column T_EEPE_NETTING (illustrative schema) → EEPE widget → iFlow report. Follow the chain requirement → computation → data.",
          "note", "Nikhil Patel", dt(2026, 9, 28), [("requirement", "REQ-CVAR-014-user-requirements.md", dt(2026, 9, 28))])
add_entry(s_cvar.id, p1.id, "Likhitha start here: which codebase serves what",
          "One codebase (ccr-risk-apps) serves CVAR iFlow AND the PFE widget pack — fix once, fix both.\nShared EEPE computation lives in CCR Data Creator, not in iFlow. Owner to talk to: Kiran Nair.\nNo need to dig through N codebases.",
          "howto", "Kiran Nair", dt(2026, 9, 1), [("kt_transcript", "KT Kiran->Likhitha 28-Aug", dt(2026, 9, 1))])
add_entry(s_cvar.id, p4.id, "Which widget answers which question (illustrative)",
          "PFE-by-netting-set widget: 'which counterparty blows up first?' EEPE-trend widget: 'is it getting worse?'\nBoth read the same EEPE endpoint as iFlow — if iFlow and the widget disagree, suspect the widget's cut-off, not the data.",
          "note", "Likhitha Sharma", dt(2026, 9, 15), [("manual", "widget-pack README (illustrative)", dt(2026, 9, 15))])
# --- AppStudio Reports ---
add_entry(s_app.id, p1.id, "Netting sets and collateral in one paragraph",
          "A netting set = trades with one counterparty under one master agreement that can be netted; collateral further cuts exposure.\nSA-CCR computes exposure per netting set, then aggregates. If one trade looks huge, check its netting set first.",
          "definition", "Manoj Iyer", dt(2026, 5, 22), [("kt_transcript", "KT Manoj 12-May", dt(2026, 5, 22))])
add_entry(s_app.id, p1.id, "Number looks off at month-end? Read this first",
          "1. Check refresh banner: data is EOD, refreshed 06:30 CET.\n2. Check caveats list for known feed issues.\n3. Compare vs last month in the Movement tab.\n\nIf still off, request a change (see Change Process) — no ticket queue needed.",
          "howto", "Girish Menon", dt(2026, 7, 15), [("manual", "analyst-runbook", dt(2026, 7, 15))])
# --- Shared Computations (p2) ---
add_entry(s_comp.id, p2.id, "The EEPE engine: one computation, three consumers",
          "eepe-engine-saccr-v2 runs once in CCR Data Creator. Consumers: CVAR Adjustment iFlow, LR Accuracy, PFE Widget Pack.\nChange it and all three move — see Downstream impact on the CCR Data Creator page before touching it.",
          "definition", "Kiran Nair", dt(2026, 8, 1), [("manual", "ccr-data-creator spec", dt(2026, 8, 1))])
add_entry(s_comp.id, p2.id, "Where the SA-CCR inputs live",
          "Trades + netting sets + collateral land in CCR_RISK_MART (illustrative schema).\nCut-off 6pm IST; late snapshots roll to next EOD and delay iFlow, LR and widgets together.",
          "howto", "Kiran Nair", dt(2026, 8, 10), [("manual", "ccr-data-creator spec", dt(2026, 8, 10))])
add_entry(s_comp.id, p2.id, "REQ-CCR-DATA-007: mart must carry netting-set EEPE",
          "From user requirement REQ-CCR-DATA-007 (attached under Documents): the mart must expose EEPE per netting set so iFlow and LR read the same column.\nOne column, three readers — that is why the mart is the lineage root.",
          "note", "Kiran Nair", dt(2026, 8, 12), [("requirement", "REQ-CCR-DATA-007-mart-requirements.md", dt(2026, 8, 12))])
# --- Leverage Ratio (p3) ---
add_entry(s_lr.id, p3.id, "SA-CCR feeds the leverage ratio",
          "LR Accuracy reads SA-CCR EAD as its exposure input: if the EEPE engine moves, the LR exposure moves with it.\nNever explain an LR move without checking whether SA-CCR moved first.",
          "definition", "Girish Menon", dt(2026, 5, 5), [("manual", "lr-accuracy spec", dt(2026, 5, 5))])
add_entry(s_lr.id, p3.id, "REQ-LR-003: LR must foot to SA-CCR EAD (illustrative)",
          "From user requirement REQ-LR-003 (attached under Documents): the LR pack must reconcile (foot) to SA-CCR EAD each month-end (illustrative tolerance).\nTrace: requirement → EEPE engine → mart → LR pack.",
          "note", "Girish Menon", dt(2026, 5, 8), [("requirement", "REQ-LR-003-leverage-requirements.md", dt(2026, 5, 8))])
# STALE entry: verified Jan, repo updated Mar
add_entry(s_lr.id, p3.id, "SA-CCR mapping csv location (STALE demo)",
          "Mapping lives in the data-pipelines repo, file mapping/saccr.csv.\n(In demo this entry is STALE because the repo updated after verification.)",
          "note", "Kiran Nair", dt(2026, 1, 15), [("repo", "github.com/socgen/ccr-data-pipelines", dt(2026, 3, 2))])
# STALE entry for the dev view: endpoint contract changed after verification
add_entry(s_comp.id, p2.id, "EEPE endpoint pagination changed (STALE demo)",
          "The /api/ccr/exposure/eepe pagination changed after this note was verified (illustrative).\nRe-check page size before reusing old client code.\n(In demo this entry is STALE because the repo updated after verification.)",
          "note", "Kiran Nair", dt(2026, 8, 20), [("repo", "github.com/socgen/ccr-data-pipelines", dt(2026, 9, 5))])
# --- Feeds, Requirements & Change: Divya-only (red single-owner topic) ---
add_entry(s_feed.id, p5.id, "Legacy SA-CCR feed frozen (illustrative)",
          "Legacy feed frozen June 2026 (illustrative). New mart is the only source dashboards should read. Legacy kept for audit only.",
          "caveat", "Divya Reddy", dt(2026, 8, 15), [("manual", "archive-runbook (illustrative)", dt(2026, 8, 15))])
add_entry(s_feed.id, None, "Feed cut-off times",
          "All CCR feeds cut off at 19:00 CET (illustrative schedule). Late trades roll to next EOD.\nOne late snapshot delays iFlow, LR and widgets together.",
          "howto", "Divya Reddy", dt(2026, 7, 1), [("manual", "ops-calendar", dt(2026, 7, 1))])
add_entry(s_chg.id, None, "How to request a change (process)",
          "1. Raise Jira tagged with the project's component (e.g. `ccr-iflow`).\n2. Tag current owner (see project page).\n3. Owner verifies + updates the knowledge entry — the entry stays fresh automatically.\nSLA: 3 business days for acknowledgement.",
          "process", "Divya Reddy", dt(2026, 7, 10), [("manual", "change-playbook", dt(2026, 7, 10))])
add_entry(s_chg.id, p1.id, "Access for new joiners",
          "Access via the CCR users group. Takes ~1 day.\nLikhitha found codebase, endpoints and owner in 2 minutes on the CVAR iFlow page instead of digging through codebases.",
          "process", "Divya Reddy", dt(2026, 8, 20), [("manual", "access-guide", dt(2026, 8, 20))])

# --- SGMR entries: reports run on how the codebases are built ---
add_entry(s_rec.id, p6.id, "What is a recon break? (plain language)",
          "A recon break = front-office feed and risk mart disagreeing beyond tolerance (illustrative tolerance).\nBreaks block month-end sign-off until explained or fixed.",
          "definition", "Girish Menon", dt(2026, 6, 5), [("manual", "sgmr-recon README", dt(2026, 6, 5))])
add_entry(s_rec.id, p6.id, "February recon spike was a late feed, not bad data (illustrative)",
          "Break counts spiked in February (illustrative figures — pattern, not real data) after a late snapshot.\nRe-running after the snapshot cleared every break. Check cut-off times before doubting the data.",
          "caveat", "Girish Menon", dt(2026, 3, 10), [("manual", "sgmr-recon runbook", dt(2026, 3, 10))])
add_entry(s_rec.id, p6.id, "Refresh cadence for SGMR reports",
          "Nightly build at 04:00 CET (illustrative schedule) from the recon engine.\nLate feeds roll to the next build and delay recon, P&L explain and sign-off together.",
          "howto", "Girish Menon", dt(2026, 7, 3), [("manual", "ops-calendar", dt(2026, 7, 3))])
add_entry(s_sgpack.id, p7.id, "What is RA consolidation?",
          "RA packs from each region are aggregated into one global view by the RA consolidator codebase.\nIf a region's pack is late, the global view shows last good — check the region feed first.",
          "definition", "Likhitha Sharma", dt(2026, 8, 5), [("manual", "ra-consolidator README", dt(2026, 8, 5))])
add_entry(s_sgpack.id, p7.id, "How to request a change on RA packs",
          "Raise Jira tagged with component `sgmr-ra` and tag the current owner (see project page).\nNew region? Its pack mapping goes in the consolidator config — see how-to-extend on this project.",
          "process", "Likhitha Sharma", dt(2026, 8, 25), [("manual", "change-playbook", dt(2026, 8, 25))])
add_entry(s_rec.id, p8.id, "P&L explain reads recon outputs (illustrative)",
          "This pack consumes the recon engine's outputs — it does not compute its own.\nIf recon breaks, the explain moves with it. Fix the engine, both reports heal.",
          "howto", "Nikhil Patel", dt(2026, 9, 10), [("manual", "pnl-explain README (illustrative)", dt(2026, 9, 10))])
add_entry(s_sgpack.id, p9.id, "Month-end sign-off checklist (illustrative)",
          "1. Recon clean (no open breaks).\n2. RA pack footed to regions.\n3. Owner acknowledgement on the project page.\nAll three live on the linked project pages — no hunting.",
          "process", "Divya Reddy", dt(2026, 9, 12), [("manual", "signoff-checklist (illustrative)", dt(2026, 9, 12))])

# --- Requirement files + mapping sheet on disk, attached to projects ---
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

def seed_file(name, text):
    path = os.path.join(UPLOAD_DIR, f"seed_{name}")
    with open(path, "w") as f:
        f.write(text)
    return name, f"seed_{name}", os.path.getsize(path)

seed_docs = []
seed_docs.append((p1.id, "Nikhil Patel", dt(2026, 9, 28), seed_file(
    "REQ-CVAR-014-user-requirements.md",
    "# REQ-CVAR-014 — CVAR iFlow user requirements (illustrative excerpt)\n\n"
    "Author: CCR users. All figures fictional patterns, never real data.\n\n"
    "1. The CVaR report MUST break the tail measure down by netting set, collateral applied.\n"
    "2. PFE widget must answer 'which counterparty blows up first?' in one glance.\n"
    "3. Month-end pack freezes T+2; late trades roll to next EOD.\n")))
seed_docs.append((p2.id, "Kiran Nair", dt(2026, 8, 12), seed_file(
    "REQ-CCR-DATA-007-mart-requirements.md",
    "# REQ-CCR-DATA-007 — CCR mart requirements (illustrative excerpt)\n\n"
    "1. Mart MUST expose EEPE per netting set (table T_EEPE_NETTING, illustrative schema).\n"
    "2. iFlow, LR Accuracy and widgets read the SAME column — one lineage root.\n"
    "3. Feed cut-off 6pm IST; late snapshots delay all consumers together.\n")))
seed_docs.append((p3.id, "Girish Menon", dt(2026, 5, 8), seed_file(
    "REQ-LR-003-leverage-requirements.md",
    "# REQ-LR-003 — Leverage ratio requirements (illustrative excerpt)\n\n"
    "1. LR pack MUST foot to SA-CCR EAD each month-end (illustrative tolerance).\n"
    "2. Any LR move must cite whether SA-CCR moved first.\n")))
seed_docs.append((p2.id, "Kiran Nair", dt(2026, 3, 2), seed_file(
    "saccr-illustrative-mapping.csv",
    "netting_set,trade_type,feed_code,mapped_type,note\n"
    "NS-101,cleared,CLR,bilateral,MARCH FIX: was mapped bilateral — corrected April (illustrative)\n"
    "NS-204,bilateral,BIL,bilateral,ok\n"
    "NS-318,cleared,CLR,cleared,ok post April mapping\n")))
for pid, by, when, (fname, stored, size) in seed_docs:
    ctype = "text/markdown" if fname.endswith(".md") else "text/csv"
    db.add(Document(project_id=pid, entry_id=None, filename=fname,
                   stored_name=stored, content_type=ctype, size_bytes=size,
                   uploaded_by=by, created_at=when))

# Demo Jira history on CCR Data Creator: 2 tickets × (ticket entry + worklogs)
from jira_mock import mock_jira_ticket
for _key in ["RISQ-4821", "RISQ-5001"]:
    _t = mock_jira_ticket(_key)
    _ver = max([_t["updated_at"]] + [_w["created"] for _w in _t["worklogs"]]) + timedelta(hours=1)
    add_entry(s_comp.id, p2.id, f"[{_key}] {_t['summary']}",
              _t["description"] + "\n\nLabels: " + ", ".join(_t["labels"]),
              "note", _t["reporter"], _ver, [("jira", _key, _t["updated_at"])])
    for _i, _w in enumerate(_t["worklogs"]):
        add_entry(s_comp.id, p2.id, f"[{_key}] worklog — {_w['author']} {_w['created'].date().isoformat()}",
                  _w["text"], "note", _w["author"], _ver, [("jira", f"{_key}#wl{_i}", _w["created"])])

db.commit()
print(f"Seeded: topics={db.query(Topic).count()} projects={db.query(Project).count()} entries={db.query(Entry).count()} documents={db.query(Document).count()}")
