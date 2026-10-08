from fastapi import FastAPI, HTTPException, Query, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import json
import os
import re
import shutil
import time
import urllib.request
import urllib.error
import uuid

from models import Base, Topic, Subtopic, Project, ProjectComponent, ProjectPerson, Attribute, Entry, Source, Document, DB_URL
from jira_mock import mock_jira_ticket, ticket_payload

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(engine)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Knowledge Repository")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def is_stale(entry: Entry, sources: list) -> bool:
    if not entry.verified_at:
        return False
    for s in sources:
        if s.source_updated_at and s.source_updated_at > entry.verified_at:
            return True
    return False

def doc_dict(d: Document) -> dict:
    return {
        "id": d.id,
        "project_id": d.project_id,
        "entry_id": d.entry_id,
        "filename": d.filename,
        "content_type": d.content_type or "",
        "size_bytes": d.size_bytes or 0,
        "uploaded_by": d.uploaded_by or "",
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "url": f"/documents/{d.id}",
    }

def entry_dict(e: Entry, db) -> dict:
    srcs = db.query(Source).filter(Source.entry_id == e.id).all()
    docs = db.query(Document).filter(Document.entry_id == e.id).all()
    return {
        "id": e.id,
        "subtopic_id": e.subtopic_id,
        "project_id": e.project_id,
        "title": e.title,
        "body": e.body,
        "entry_kind": e.entry_kind,
        "author": e.author,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "verified_at": e.verified_at.isoformat() if e.verified_at else None,
        "stale": is_stale(e, srcs),
        "documents": [doc_dict(d) for d in docs],
        "sources": [
            {"id": s.id, "source_type": s.source_type, "source_ref": s.source_ref,
             "source_updated_at": s.source_updated_at.isoformat() if s.source_updated_at else None}
            for s in srcs
        ],
    }

# ---------- Knowledge side ----------

@app.get("/topics")
def list_topics():
    db = SessionLocal()
    try:
        topics = db.query(Topic).all()
        out = []
        for t in topics:
            sub_count = db.query(func.count(Subtopic.id)).filter(Subtopic.topic_id == t.id).scalar()
            out.append({"id": t.id, "name": t.name, "description": t.description, "subtopic_count": sub_count})
        return out
    finally:
        db.close()

@app.get("/topics/{topic_id}")
def topic_detail(topic_id: int):
    db = SessionLocal()
    try:
        t = db.query(Topic).filter(Topic.id == topic_id).first()
        if not t:
            raise HTTPException(404, "topic not found")
        subs = db.query(Subtopic).filter(Subtopic.topic_id == topic_id).all()
        sub_ids = [s.id for s in subs]
        entries = db.query(Entry).filter(Entry.subtopic_id.in_(sub_ids)).all() if sub_ids else []
        projects = db.query(Project).filter(Project.subtopic_id.in_(sub_ids)).all() if sub_ids else []
        entry_payload = [entry_dict(e, db) for e in entries]
        fresh = sum(1 for e in entry_payload if not e["stale"])
        total = len(entry_payload)
        return {
            "id": t.id, "name": t.name, "description": t.description,
            "subtopics": [{"id": s.id, "name": s.name} for s in subs],
            "entries": entry_payload,
            "projects": [{"id": p.id, "name": p.name, "status": p.status, "owner_name": p.owner_name, "summary": p.summary} for p in projects],
            "health": {"total_entries": total, "fresh": fresh,
                        "fresh_pct": round(100 * fresh / total, 1) if total else 100.0},
        }
    finally:
        db.close()

@app.get("/entries/{entry_id}")
def entry_detail(entry_id: int):
    db = SessionLocal()
    try:
        e = db.query(Entry).filter(Entry.id == entry_id).first()
        if not e:
            raise HTTPException(404, "entry not found")
        d = entry_dict(e, db)
        proj = None
        if e.project_id:
            p = db.query(Project).filter(Project.id == e.project_id).first()
            if p:
                proj = {"id": p.id, "name": p.name, "status": p.status, "owner_name": p.owner_name, "summary": p.summary}
        d["project"] = proj
        return d
    finally:
        db.close()

@app.patch("/entries/{entry_id}/verify")
def verify_entry(entry_id: int):
    # Human re-attestation: verified now, so the read logic flips it FRESH.
    db = SessionLocal()
    try:
        e = db.query(Entry).filter(Entry.id == entry_id).first()
        if not e:
            raise HTTPException(404, "entry not found")
        e.verified_at = datetime.utcnow()
        db.commit()
        return entry_dict(e, db)
    finally:
        db.close()

@app.get("/health/{topic_id}")
def health(topic_id: int):
    db = SessionLocal()
    try:
        subs = db.query(Subtopic).filter(Subtopic.topic_id == topic_id).all()
        sub_ids = [s.id for s in subs]
        entries = db.query(Entry).filter(Entry.subtopic_id.in_(sub_ids)).all() if sub_ids else []
        projects = db.query(Project).filter(Project.subtopic_id.in_(sub_ids)).all() if sub_ids else []
        payload = [entry_dict(e, db) for e in entries]
        fresh = sum(1 for e in payload if not e["stale"])
        total = len(payload)
        contributors = sorted({e["author"] for e in payload if e["author"]})
        single_owner = len(contributors) <= 1
        stalest = sorted([e for e in payload if e["stale"]], key=lambda x: x["id"])[:5]
        return {
            "topic_id": topic_id,
            "contributor_count": len(contributors),
            "contributors": contributors,
            "total_entries": total,
            "fresh_pct": round(100 * fresh / total, 1) if total else 100.0,
            "single_owner": single_owner,
            "stalest_entries": [{"id": e["id"], "title": e["title"]} for e in stalest],
        }
    finally:
        db.close()

# ---------- Project / dev side ----------

@app.get("/projects")
def list_projects(topic_id: Optional[int] = None):
    db = SessionLocal()
    try:
        q = db.query(Project)
        if topic_id:
            subs = db.query(Subtopic).filter(Subtopic.topic_id == topic_id).all()
            sub_ids = [s.id for s in subs]
            q = q.filter(Project.subtopic_id.in_(sub_ids)) if sub_ids else q.filter(False)
        projects = q.all()
        return [{"id": p.id, "name": p.name, "status": p.status, "owner_name": p.owner_name,
                 "summary": p.summary, "subtopic_id": p.subtopic_id} for p in projects]
    finally:
        db.close()

@app.get("/projects/{project_id}")
def project_detail(project_id: int):
    db = SessionLocal()
    try:
        p = db.query(Project).filter(Project.id == project_id).first()
        if not p:
            raise HTTPException(404, "project not found")
        comps = db.query(ProjectComponent).filter(ProjectComponent.project_id == p.id).all()
        people = db.query(ProjectPerson).filter(ProjectPerson.project_id == p.id).all()
        attrs = db.query(Attribute).filter(Attribute.owner_type == "project", Attribute.owner_id == p.id).all()
        linked = db.query(Entry).filter(Entry.project_id == p.id).all()
        related = db.query(Project).filter(Project.subtopic_id == p.subtopic_id, Project.id != p.id).all()
        sub = db.query(Subtopic).filter(Subtopic.id == p.subtopic_id).first()
        docs = db.query(Document).filter(Document.project_id == p.id).all()
        # Lineage: components are shared when their ref matches byte-identically
        # (same codebase / computation / endpoint / database reused downstream).
        all_comps = db.query(ProjectComponent).all()
        by_ref = {}
        for c in all_comps:
            key = (c.ref or "").strip().lower()
            if key:
                by_ref.setdefault(key, []).append(c)
        proj_names = {x.id: (x.name, x.status) for x in db.query(Project).all()}
        comp_payload = []
        shared = {}  # other_project_id -> list of shared {kind, ref, label}
        for c in comps:
            key = (c.ref or "").strip().lower()
            others = sorted({x.project_id for x in by_ref.get(key, []) if x.project_id != p.id}) if key else []
            used_by = [{"id": oid, "name": proj_names[oid][0], "status": proj_names[oid][1]} for oid in others if oid in proj_names]
            comp_payload.append({"id": c.id, "kind": c.kind, "label": c.label, "ref": c.ref, "notes": c.notes,
                                 "used_by": used_by, "used_by_count": len(used_by)})
            for oid in others:
                if oid in proj_names:
                    shared.setdefault(oid, []).append({"kind": c.kind, "ref": c.ref, "label": c.label})
        shared_related = [{"id": oid, "name": proj_names[oid][0], "status": proj_names[oid][1], "shared": items}
                          for oid, items in sorted(shared.items(), key=lambda kv: -len(kv[1]))]
        lineage = [c for c in comp_payload if c["used_by_count"] > 0]
        return {
            "id": p.id, "name": p.name, "summary": p.summary, "status": p.status,
            "owner_name": p.owner_name, "subtopic_id": p.subtopic_id,
            "subtopic_name": sub.name if sub else "",
            "documents": [doc_dict(d) for d in docs],
            "components": comp_payload,
            "people": [{"person_name": x.person_name, "role": x.role} for x in people],
            "attributes": [{"key": a.key, "value": a.value} for a in attrs],
            "entries": [entry_dict(e, db) for e in linked],
            "related_projects": [{"id": r.id, "name": r.name, "status": r.status} for r in related],
            "shared_related": shared_related,
            "lineage": lineage,
        }
    finally:
        db.close()

class ProjectCreate(BaseModel):
    name: str
    subtopic_id: int
    summary: str
    status: str = "live"
    owner: str = ""
    components: Optional[List[dict]] = []
    attributes: Optional[List[dict]] = []

@app.post("/projects")
def create_project(body: ProjectCreate):
    # MAX 5 required fields: name, subtopic, summary, status, owner
    if not body.name or not body.subtopic_id or not body.summary or not body.status or not body.owner:
        raise HTTPException(400, "5 required fields: name, subtopic_id, summary, status, owner")
    db = SessionLocal()
    try:
        sub = db.query(Subtopic).filter(Subtopic.id == body.subtopic_id).first()
        if not sub:
            raise HTTPException(400, "invalid subtopic_id")
        p = Project(name=body.name, subtopic_id=body.subtopic_id, summary=body.summary,
                    status=body.status, owner_name=body.owner)
        db.add(p); db.flush()
        for c in (body.components or []):
            db.add(ProjectComponent(project_id=p.id, kind=c.get("kind", "other"),
                                    label=c.get("label", ""), ref=c.get("ref", ""), notes=c.get("notes", "")))
        for a in (body.attributes or []):
            if a.get("key"):
                db.add(Attribute(owner_type="project", owner_id=p.id, key=a["key"], value=a.get("value", "")))
        db.add(ProjectPerson(project_id=p.id, person_name=body.owner, role="owner"))
        db.commit()
        return {"id": p.id, "name": p.name}
    finally:
        db.close()

class ComponentCreate(BaseModel):
    kind: str = "other"
    label: str = ""
    ref: str = ""
    notes: str = ""

@app.post("/projects/{project_id}/components")
def add_component(project_id: int, body: ComponentCreate):
    db = SessionLocal()
    try:
        p = db.query(Project).filter(Project.id == project_id).first()
        if not p:
            raise HTTPException(404, "project not found")
        c = ProjectComponent(project_id=project_id, kind=body.kind, label=body.label, ref=body.ref, notes=body.notes)
        db.add(c); db.commit()
        return {"id": c.id}
    finally:
        db.close()

class AttributeCreate(BaseModel):
    key: str
    value: str = ""

@app.post("/projects/{project_id}/attributes")
def add_attribute(project_id: int, body: AttributeCreate):
    db = SessionLocal()
    try:
        p = db.query(Project).filter(Project.id == project_id).first()
        if not p:
            raise HTTPException(404, "project not found")
        a = Attribute(owner_type="project", owner_id=project_id, key=body.key, value=body.value)
        db.add(a); db.commit()
        return {"id": a.id}
    finally:
        db.close()

class EntryCreate(BaseModel):
    title: str
    body: str = ""
    entry_kind: str = "note"
    author: str = ""
    subtopic_id: Optional[int] = None
    source_type: str = "manual"
    source_ref: str = ""

@app.post("/projects/{project_id}/entries")
def add_entry_to_project(project_id: int, body: EntryCreate):
    # Add knowledge straight to a living project page (note or KT-approved draft).
    if not (body.title or "").strip():
        raise HTTPException(400, "title required")
    db = SessionLocal()
    try:
        p = db.query(Project).filter(Project.id == project_id).first()
        if not p:
            raise HTTPException(404, "project not found")
        subtopic_id = body.subtopic_id or p.subtopic_id
        if not db.query(Subtopic).filter(Subtopic.id == subtopic_id).first():
            raise HTTPException(400, "invalid subtopic_id")
        now = datetime.utcnow()
        e = Entry(subtopic_id=subtopic_id, project_id=project_id,
                  title=body.title[:120], body=body.body,
                  entry_kind=body.entry_kind or "note",
                  author=body.author or p.owner_name or "manual-add",
                  verified_at=now)
        db.add(e); db.flush()
        db.add(Source(entry_id=e.id, source_type=body.source_type or "manual",
                      source_ref=body.source_ref or "project-page", source_updated_at=now))
        db.commit()
        return {"entry_id": e.id, "title": e.title}
    finally:
        db.close()

# ---------- Documents (upload once, live with the project) ----------

@app.post("/documents/upload")
def upload_document(
    file: UploadFile = File(...),
    project_id: Optional[int] = Form(None),
    entry_id: Optional[int] = Form(None),
    uploaded_by: Optional[str] = Form(""),
):
    # No content parsing: store bytes on disk, metadata in DB.
    if not project_id and not entry_id:
        raise HTTPException(400, "attach to a project_id and/or entry_id")
    db = SessionLocal()
    try:
        if project_id:
            if not db.query(Project).filter(Project.id == project_id).first():
                raise HTTPException(400, "invalid project_id")
        if entry_id:
            e = db.query(Entry).filter(Entry.id == entry_id).first()
            if not e:
                raise HTTPException(400, "invalid entry_id")
            if not project_id:
                project_id = e.project_id
        original = os.path.basename(file.filename or "upload.bin")
        stored = f"{uuid.uuid4().hex}_{original}"
        dest = os.path.join(UPLOAD_DIR, stored)
        with open(dest, "wb") as out:
            shutil.copyfileobj(file.file, out)
        d = Document(project_id=project_id, entry_id=entry_id, filename=original,
                     stored_name=stored, content_type=file.content_type or "",
                     size_bytes=os.path.getsize(dest), uploaded_by=uploaded_by or "")
        db.add(d); db.commit()
        return doc_dict(d)
    finally:
        db.close()

@app.get("/documents")
def list_documents(project_id: Optional[int] = None, entry_id: Optional[int] = None):
    db = SessionLocal()
    try:
        q = db.query(Document)
        if project_id:
            q = q.filter(Document.project_id == project_id)
        if entry_id:
            q = q.filter(Document.entry_id == entry_id)
        return [doc_dict(d) for d in q.order_by(Document.id).all()]
    finally:
        db.close()

@app.get("/documents/{doc_id}")
def download_document(doc_id: int):
    db = SessionLocal()
    try:
        d = db.query(Document).filter(Document.id == doc_id).first()
        if not d:
            raise HTTPException(404, "document not found")
        path = os.path.join(UPLOAD_DIR, d.stored_name)
        if not os.path.isfile(path):
            raise HTTPException(404, "file missing on disk")
        return FileResponse(path, media_type=d.content_type or "application/octet-stream", filename=d.filename)
    finally:
        db.close()

# ---------- Chat (deterministic retrieval over the repo — no LLM, offline) ----------

REQUESTY_URL = "https://router.requesty.ai/v1/chat/completions"
REQUESTY_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"
SYSTEM_PROMPT = (
    "You are the TeamRiskFusion assistant, a knowledgeable teammate on a bank risk-IT team. "
    "The user asks about THEIR team's knowledge repo — answer in natural, conversational "
    "language like a helpful colleague: direct answer first (1-2 sentences), then the useful "
    "detail, naming the entry, project, or widget it comes from.\n"
    "RULES: Use ONLY the REPO CONTEXT below. If the answer isn't there, say plainly you "
    "couldn't find it and suggest logging it via Knowledge Feed. Never invent API endpoints, database "
    "names, numbers, owners, or dates. Max 150 words unless asked for detail. No preamble "
    "about your process, no analysis of the question — just answer."
)

_requesty_key = None
_requesty_key_source = "missing"

def requesty_key() -> str:
    """Server-side only. Env var wins; else backend/.env (never committed, never sent out)."""
    global _requesty_key, _requesty_key_source
    if _requesty_key is None:
        _requesty_key = os.environ.get("REQUESTY_API_KEY", "") or ""
        if _requesty_key:
            _requesty_key_source = "env"
        else:
            try:
                with open(os.path.join(os.path.dirname(__file__), ".env")) as f:
                    for line in f:
                        s = line.strip()
                        if s.startswith("REQUESTY_API_KEY"):
                            _, _, v = s.partition("=")
                            _requesty_key = v.strip().strip('"').strip("'")
                            break
                if _requesty_key:
                    _requesty_key_source = "dotenv"
            except OSError:
                pass
    return _requesty_key or ""

@app.get("/chat/status")
def chat_status():
    """Decisive self-diagnosis (browser-openable). Never exposes the key."""
    key = requesty_key()
    return {"model": REQUESTY_MODEL, "url": REQUESTY_URL,
            "key_present": bool(key), "key_source": _requesty_key_source if key else "missing",
            "key_len": len(key),
            "fallback": "deterministic retrieval (quoted entries, no hallucination)"}

def _chat_scope(db, topic_id, project_id):
    if project_id:
        p = db.query(Project).filter(Project.id == project_id).first()
        if not p:
            raise HTTPException(400, "invalid project_id")
        entries = db.query(Entry).filter(Entry.project_id == p.id).all()
        return entries, [p], f"scoped to {p.name}"
    if topic_id:
        subs = db.query(Subtopic).filter(Subtopic.topic_id == topic_id).all()
        sub_ids = [s.id for s in subs]
        entries = db.query(Entry).filter(Entry.subtopic_id.in_(sub_ids)).all() if sub_ids else []
        projects = db.query(Project).filter(Project.subtopic_id.in_(sub_ids)).all() if sub_ids else []
        t = db.query(Topic).filter(Topic.id == topic_id).first()
        return entries, projects, f"scoped to {t.name}" if t else "this topic"
    return db.query(Entry).all(), db.query(Project).all(), "the whole repo"

def _retrieve_hits(db, toks, entry_payload, projects):
    ranked_e = sorted(entry_payload,
                      key=lambda e: chat_overlap(toks, e["title"], 3) + chat_overlap(toks, e["body"], 1),
                      reverse=True)
    hits_e = [e for e in ranked_e
              if chat_overlap(toks, e["title"], 3) + chat_overlap(toks, e["body"], 1) >= 2][:3]
    ranked_p = sorted(projects, key=lambda x: proj_score(db, toks, x), reverse=True)
    hits_p = [x for x in ranked_p if proj_score(db, toks, x) >= 2][:2]
    comp_hits = []
    for x in hits_p:
        for c in db.query(ProjectComponent).filter(ProjectComponent.project_id == x.id).all():
            if chat_overlap(toks, f"{c.label} {c.ref}", 2) > 0 and len(comp_hits) < 4:
                comp_hits.append({"project_id": x.id, "project_name": x.name, "kind": c.kind,
                                  "label": c.label, "ref": c.ref})
    ctx_e = ranked_e[:6]  # broader set for AI context (nav still shows top 3)
    return hits_e, hits_p, comp_hits, ctx_e

CHAT_STOPWORDS = {"the", "a", "an", "is", "are", "was", "were", "what", "when", "where",
    "who", "how", "why", "which", "do", "does", "did", "to", "of", "in", "on", "for",
    "and", "or", "it", "its", "this", "that", "i", "you", "me", "my", "our", "please",
    "tell", "show", "find", "get", "give", "about", "with", "by", "from", "at", "as",
    "no", "not", "nor", "yes",
    "such", "thing", "things", "same", "just", "than", "then", "them", "they", "will",
    "over", "under", "more", "most", "some", "any", "all", "each", "other", "into",
    "been", "also", "only", "very", "much", "many", "well", "back", "here", "there",
    "their", "these", "those", "out", "up", "down", "off", "per", "via", "using",
    "used", "use", "within", "without", "between", "both", "whether", "while",
    "during", "before", "after", "again", "once"}

def chat_norm(text: str) -> str:
    return re.sub(r"[-_]", "", (text or "").lower())

def chat_tokens(text: str) -> list:
    toks = [chat_norm(w) for w in re.findall(r"[a-z0-9/._-]+", (text or "").lower())
            if w not in CHAT_STOPWORDS and len(w) > 1]
    # crude plurals so "widgets" also matches "widget"
    toks += [t[:-1] for t in toks if t.endswith("s") and len(t) > 3 and not t.endswith("ss")]
    return toks

def chat_overlap(toks: list, text: str, weight: int = 1) -> int:
    hay = chat_norm(text)
    return sum(weight for t in toks if t and t in hay)

def proj_score(db, toks: list, x) -> int:
    s = chat_overlap(toks, x.name, 3) + chat_overlap(toks, x.summary, 1)
    for c in db.query(ProjectComponent).filter(ProjectComponent.project_id == x.id).all():
        s = max(s, chat_overlap(toks, f"{c.label} {c.ref}", 2))
    return s

class ChatIn(BaseModel):
    message: str
    topic_id: Optional[int] = None
    project_id: Optional[int] = None

@app.post("/chat/ask")
def chat_ask(body: ChatIn):
    msg = (body.message or "").strip()
    if not msg:
        raise HTTPException(400, "empty message")
    low = msg.lower()
    db = SessionLocal()
    try:
        entries, projects, scope = _chat_scope(db, body.topic_id, body.project_id)
        entry_payload = [entry_dict(e, db) for e in entries]

        # greeting
        if re.search(r"\b(hi|hello|hey|namaste|good (morning|afternoon|evening))\b", low) and len(chat_tokens(msg)) <= 3:
            return {"answer": "Hi — I answer only from your repo, nothing generated. Ask about a metric, "
                              "who owns something, refresh times, or what's stale.",
                    "entries": [], "projects": [], "components": []}
        # owner intent
        if re.search(r"\bwho\s+(owns|built|maintains|supports)\b|\bowner of\b|\bowned by\b", low):
            toks = chat_tokens(msg)
            ranked = sorted(projects, key=lambda x: proj_score(db, toks, x), reverse=True)
            best = ranked[0] if ranked and proj_score(db, toks, ranked[0]) > 0 else None
            if best:
                owners = [x.person_name for x in db.query(ProjectPerson).filter(
                    ProjectPerson.project_id == best.id, ProjectPerson.role == "owner").all()]
                built = f"Built by {owners[0]}. " if owners else ""
                return {"answer": f"{best.name} is owned now by {best.owner_name} ({best.status}). {built}"
                                  f"Everything below is quoted from your repo.",
                        "entries": [], "projects": [{"id": best.id, "name": best.name, "status": best.status,
                                                     "owner_name": best.owner_name}], "components": []}
            return {"answer": f"I couldn't match that to a project in {scope}. Try the exact project name.",
                    "entries": [], "projects": [], "components": []}
        # stale intent
        if "stale" in low:
            stale = [e for e in entry_payload if e["stale"]][:5]
            if not stale:
                return {"answer": f"Nothing stale in {scope} — every entry is verified after its sources.",
                        "entries": [], "projects": [], "components": []}
            return {"answer": f"{len(stale)} stale entr{'y' if len(stale) == 1 else 'ies'} in {scope} "
                              f"(source changed after verification). Open one to re-verify:",
                    "entries": [{"id": e["id"], "title": e["title"], "entry_kind": e["entry_kind"],
                                 "stale": True, "author": e["author"]} for e in stale],
                    "projects": [], "components": []}
        # keyword retrieval
        toks = chat_tokens(msg)
        if not toks:
            return {"answer": "Try fewer, more specific words — e.g. a metric, endpoint, or project name.",
                    "entries": [], "projects": [], "components": []}
        hits_e, hits_p, comp_hits, _ctx = _retrieve_hits(db, toks, entry_payload, projects)
        if not hits_e and not hits_p:
            return {"answer": f"Nothing in {scope} matches “{msg}”. Try fewer words — or capture it "
                              f"so the next person finds it.",
                    "entries": [], "projects": [], "components": []}
        return {"answer": f"Here's what your repo says about “{msg}” ({scope}) — quoted, not generated:",
                "entries": [{"id": e["id"], "title": e["title"], "entry_kind": e["entry_kind"],
                             "stale": e["stale"], "author": e["author"]} for e in hits_e],
                "projects": [{"id": x.id, "name": x.name, "status": x.status,
                              "owner_name": x.owner_name} for x in hits_p],
                "components": comp_hits}
    finally:
        db.close()

def _clean_answer(text: str):
    """Strip <think> reasoning blocks; quarantine leaked chain-of-thought.
    Returns clean text, a rescued tail, or None (caller falls back)."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL).strip()
    low = text.lower()
    leaked = ("thinking process" in low or "chain-of-thought" in low
              or ("analyze user input" in low and "check constraints" in low))
    if not leaked:
        return text or None
    m = re.search(r"(?is)(?:^|\n)\s*(?:final answer|final response|^answer|^response|in short|to summarize)\s*[:—–-]\s*(.+)$",
                  text)
    if m and len(m.group(1).strip()) > 20:
        return m.group(1).strip()
    return None

class ChatAIIn(BaseModel):
    message: str
    topic_id: Optional[int] = None
    project_id: Optional[int] = None
    history: Optional[List[dict]] = []

def _grounded_fallback(msg: str, scope: str, hits_e: list, hits_p: list, comp_hits: list,
                       mode: str = "retrieval") -> dict:
    if not hits_e and not hits_p:
        return {"answer": f"Nothing in {scope} matches “{msg}”. Try fewer words — or capture it "
                          f"so the next person finds it.",
                "entries": [], "projects": [], "components": [], "mode": mode}
    snippets = []
    for e in hits_e[:4]:
        text = re.sub(r"\s+", " ", e.get("body") or "").strip()
        if text:
            snippets.append(f"{e['title']}: {text[:280]}{'…' if len(text) > 280 else ''}")
    answer = f"Based on the knowledge in {scope}, here’s the answer to “{msg}”:"
    if snippets:
        answer += "\n\n" + "\n\n".join(snippets)
    elif hits_p:
        answer += "\n\n" + "\n".join(
            f"{p.name} is {p.status} and is owned by {p.owner_name}."
            for p in hits_p[:2]
        )
    return {"answer": answer,
            "entries": [{"id": e["id"], "title": e["title"], "entry_kind": e["entry_kind"],
                         "stale": e["stale"], "author": e["author"]} for e in hits_e],
            "projects": [{"id": x.id, "name": x.name, "status": x.status,
                          "owner_name": x.owner_name} for x in hits_p],
            "components": comp_hits, "mode": mode}

def _metric_answer(msg: str, scope: str, entry_payload: list) -> Optional[str]:
    """Answer metric-catalog questions from definitions already stored in the repo."""
    if not re.search(r"\b(metrics?|measures?|indicators?|kpis?)\b", msg.lower()):
        return None
    definitions = []
    for term in ("cvar", "pfe", "eepe", "ead"):
        matches = [e for e in entry_payload
                   if re.search(rf"\b{term}\b", f"{e['title']} {e['body']}", re.IGNORECASE)]
        if not matches:
            continue
        entry = next((e for e in matches
                      if re.search(rf"\b{re.escape(term)}\b", e["title"], re.IGNORECASE)),
                     next((e for e in matches if e["entry_kind"] == "definition"), matches[0]))
        body = re.sub(r"\s+", " ", entry.get("body") or "").strip()
        if body:
            formula = re.search(rf"\b{re.escape(term)}\s*=\s*[^.]+", body, re.IGNORECASE)
            first = formula.group(0).strip() if formula else re.split(r"(?<=[.!?])\s+", body)[0]
            definitions.append(f"{term.upper()}: {first}")
    if not definitions:
        return None
    return f"The repo documents these CCR metrics in {scope}:\n\n" + "\n\n".join(definitions)

@app.post("/chat/ai")
def chat_ai(body: ChatAIIn):
    """Repo-grounded Nemotron answer. No key / no network / model error →
    deterministic retrieval fallback (same honesty, no hallucination)."""
    msg = (body.message or "").strip()
    if not msg:
        raise HTTPException(400, "empty message")
    low = msg.lower()
    low = re.sub(r"\bare\s*u\b", "are u", low)  # "who areu" -> "who are u"
    low = re.sub(r"\bwho r\b", "who are", low)  # "who r u" -> "who are u"
    db = SessionLocal()
    try:
        entries, projects, scope = _chat_scope(db, body.topic_id, body.project_id)
        entry_payload = [entry_dict(e, db) for e in entries]
        # small talk never reaches the model — answer like a human, instantly
        if (re.search(r"\b(hi|hello|hey|helo|hii+|heyy+|namaste|thanks|thank you|bye|ok|okay|good (morning|afternoon|evening))\b", low)
                and len(chat_tokens(msg)) <= 3):
            return {"answer": f"Hi 👋 — I know {scope}: {len(entries)} entries across {len(projects)} projects. "
                              f"Ask about a metric, an owner, an endpoint, or what's stale.",
                    "entries": [], "projects": [], "components": [], "mode": "greeting"}
        if (re.search(r"\bwho are (you|u)\b|\bwhat are you\b|\byour name\b|\babout yourself\b"
                      r"|\bwhat can you do\b|\b^(help|help me)\b", low)
                and len(chat_tokens(msg)) <= 4):
            return {"answer": f"I'm the TeamRiskFusion assistant — I know {scope}: {len(entries)} entries "
                              f"across {len(projects)} projects (metrics, owners, endpoints, refresh times, "
                              f"what's stale). Ask me anything about the team's work; for anything I don't "
                              f"have, I'll point you to the Knowledge Feed.",
                    "entries": [], "projects": [], "components": [], "mode": "greeting"}
        # owner + stale intents reuse the deterministic endpoint's exact logic
        if (re.search(r"\bwho\s+(owns|built|maintains|supports)\b|\bowner of\b|\bowned by\b", low)
                or "stale" in low):
            return chat_ask(ChatIn(message=msg, topic_id=body.topic_id, project_id=body.project_id))
        toks = chat_tokens(msg)
        if not toks:
            out = _grounded_fallback(msg, scope, [], [], [])
            out["answer"] = "Try fewer, more specific words — e.g. a metric, endpoint, or project name."
            return out
        hits_e, hits_p, comp_hits, ctx_e = _retrieve_hits(db, toks, entry_payload, projects)
        if not hits_e and not hits_p:
            print(f"[chat/ai] mode=retrieval reason=no-grounding q={msg[:60]!r}")
            return _grounded_fallback(msg, scope, [], [], [])
        metric_answer = _metric_answer(msg, scope, entry_payload)
        if metric_answer:
            out = _grounded_fallback(msg, scope, hits_e, hits_p, comp_hits, mode="retrieval")
            out["answer"] = metric_answer
            return out
        key = requesty_key()
        if not key:
            print(f"[chat/ai] mode=no-key reason=REQUESTY_API_KEY-missing q={msg[:60]!r}")
            out = _grounded_fallback(msg, scope, hits_e, hits_p, comp_hits, mode="no-key")
            out["answer"] = ("AI answering is off (no API key on the server) — here’s what the repo "
                             "says instead:") + "\n\n" + "\n".join(f"• {e['title']}" for e in hits_e[:3])
            return out
        submap = {}
        for s in db.query(Subtopic).all():
            t = db.query(Topic).filter(Topic.id == s.topic_id).first()
            submap[s.id] = (s.name, t.name if t else "")
        ctx = []
        for e in ctx_e:
            sub, top = submap.get(e["subtopic_id"], ("", ""))
            ctx.append(f"ENTRY: {e['title']} [{e['entry_kind']}, {top} › {sub}"
                       f"{', STALE — verify before trusting' if e['stale'] else ''}]\n{e['body'][:1500]}")
        for x in hits_p[:3]:
            ctx.append(f"PROJECT: {x.name} ({x.status}) — owner {x.owner_name}\n{(x.summary or '')[:500]}")
        for c in comp_hits[:8]:
            ctx.append(f"COMPONENT [{c['kind']}] {c['label']} — {c['ref']} (in {c['project_name']})")
        messages = [{"role": "system", "content": SYSTEM_PROMPT + "\n\nREPO CONTEXT:\n" + "\n\n".join(ctx)}]
        for h in (body.history or [])[-6:]:
            if isinstance(h, dict) and h.get("role") in ("user", "assistant") and isinstance(h.get("content"), str):
                messages.append({"role": h["role"], "content": h["content"][:2000]})
        messages.append({"role": "user", "content": f"({scope}) {msg}"})
        def _call_model():
            req = urllib.request.Request(
                REQUESTY_URL,
                data=json.dumps({"model": REQUESTY_MODEL, "messages": messages,
                                 "temperature": 1.0, "top_p": 0.95, "max_tokens": 400}).encode(),
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
            req.add_header("Authorization", "Bearer " + key)
            with urllib.request.urlopen(req, timeout=120) as r:
                payload = json.loads(r.read().decode())
            answer = payload["choices"][0]["message"]["content"].strip()
            if not answer:
                raise ValueError("empty model reply")
            return answer
        try:
            try:
                answer = _call_model()
            except urllib.error.HTTPError as e429:
                if e429.code != 429:
                    raise
                print(f"[chat/ai] retrying after 429 q={msg[:60]!r}")
                time.sleep(8)
                answer = _call_model()
        except urllib.error.HTTPError as e:
            code = e.code
            try:
                detail = e.read().decode()[:200]
            except Exception:
                detail = ""
            print(f"[chat/ai] mode=throttled reason=HTTP-{code} {detail[:120]!r} q={msg[:60]!r}")
            if code == 429:
                out = _grounded_fallback(msg, scope, hits_e, hits_p, comp_hits, mode="throttled")
                out["answer"] = ("The model is throttled right now — here’s the repo answer instead, "
                                 "retry the AI wording in a bit:") + "\n\n" + out["answer"]
                return out
            if code in (401, 403):
                out = _grounded_fallback(msg, scope, hits_e, hits_p, comp_hits, mode="no-key")
                out["answer"] = ("The server rejected the API key — here’s the repo answer instead; "
                                 "check REQUESTY_API_KEY in backend/.env:") + "\n\n" + out["answer"]
                return out
            print(f"[chat/ai] mode=retrieval reason=HTTP-{code} q={msg[:60]!r}")
            return _grounded_fallback(msg, scope, hits_e, hits_p, comp_hits)
        except Exception as e:
            print(f"[chat/ai] mode=retrieval reason={type(e).__name__} q={msg[:60]!r}")
            return _grounded_fallback(msg, scope, hits_e, hits_p, comp_hits)
        clean = _clean_answer(answer)
        if clean is None:
            return _grounded_fallback(msg, scope, hits_e, hits_p, comp_hits)
        return {"answer": clean,
                "entries": [{"id": e["id"], "title": e["title"], "entry_kind": e["entry_kind"],
                             "stale": e["stale"], "author": e["author"]} for e in hits_e],
                "projects": [{"id": x.id, "name": x.name, "status": x.status,
                              "owner_name": x.owner_name} for x in hits_p],
                "components": comp_hits, "mode": "ai"}
    finally:
        db.close()

# ---------- Document import: messy doc(s) in, structured draft out ----------

@app.post("/ingest/document")
def ingest_document(file: List[UploadFile] = File(...)):
    from doc_ingest import extract_text, regex_draft, sanitize_draft, pick_draft_json, EXTRACT_PROMPT
    uploads = file if isinstance(file, list) else [file]
    texts, filenames, warnings = [], [], []
    for up in uploads:
        name = os.path.basename(up.filename or "upload.bin")
        try:
            texts.append(f"\n\n===== FILE: {name} =====\n" + extract_text(name, up.file.read()))
            filenames.append(name)
        except ValueError as ve:
            warnings.append({"filename": name, "error": str(ve)})
    if not texts:
        raise HTTPException(400, "; ".join(w["error"] + f" ({w['filename']})" for w in warnings) or "no readable files")
    text = "\n".join(texts)
    result = {"filenames": filenames, "filename": filenames[0], "warnings": warnings}
    key = requesty_key()
    if key:
        raw_preview = ""
        base_messages = [
            {"role": "system", "content": "Your ENTIRE reply must be exactly one JSON object starting with { and ending with }. No analysis, no explanation, no other text before or after."},
            {"role": "user", "content": EXTRACT_PROMPT.replace("{TEXT}", text)}]
        def _extract_call(messages):
            req = urllib.request.Request(
                REQUESTY_URL,
                data=json.dumps({"model": REQUESTY_MODEL, "messages": messages,
                                 "temperature": 0.1, "top_p": 0.95, "max_tokens": 2500,
                                 "response_format": {"type": "json_object"}}).encode(),
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(req, timeout=90) as r:
                payload = json.loads(r.read().decode())
            return payload["choices"][0]["message"]["content"]
        try:
            raw = _extract_call(base_messages)
            raw_preview = raw[:150]
            raw = re.sub(r"```(?:json)?", "", raw).strip()
            obj = pick_draft_json(raw)
            if obj is None:
                # one stern retry: feed back the analysis, demand only the object
                raw = _extract_call(base_messages + [
                    {"role": "assistant", "content": raw[:800]},
                    {"role": "user", "content": "That was analysis, not the deliverable. Reply with ONLY the JSON object specified — no other text."}])
                raw_preview = raw[:150]
                raw = re.sub(r"```(?:json)?", "", raw).strip()
                obj = pick_draft_json(raw)
            if obj is None:
                raise ValueError("no parseable JSON object in reply")
            draft = sanitize_draft(obj, result["filenames"][0])
            print(f"[ingest/document] mode=ai files={result['filenames']} chars={len(text)} "
                  f"keys={list(obj.keys())} ncomp={len(obj.get('components', []) or [])}")
            return {**result, "mode": "ai", "chars": len(text), **draft}
        except Exception as e:
            print(f"[ingest/document] mode=regex reason={type(e).__name__} preview={raw_preview[:120]!r} files={result['filenames']}")
    draft = regex_draft(text, " + ".join(result["filenames"]))
    return {**result, "mode": "regex", "chars": len(text), **draft}

# ---------- Ingestion (deterministic, no LLM) ----------

class TranscriptIn(BaseModel):
    text: str
    subtopic_id: Optional[int] = None

def parse_transcript(text: str):
    """Deterministic parsing only: split on speaker turns / headings / Q&A blocks."""
    lines = [l.strip() for l in text.splitlines()]
    blocks = []
    current_speaker = "Note"
    current_lines: list = []
    speaker_re = re.compile(r"^([A-Z][A-Za-z .'-]{1,30}):\s*(.*)$")
    heading_re = re.compile(r"^(#{1,3}\s+|Q:\s*|Question\s*\d*\s*:\s*|A:\s*|Answer\s*\d*\s*:\s*)(.*)$", re.IGNORECASE)

    def flush():
        nonlocal current_lines
        body = "\n".join(current_lines).strip()
        if body:
            blocks.append({"speaker": current_speaker, "body": body})
        current_lines = []

    for line in lines:
        if not line:
            if current_lines:
                current_lines.append("")
            continue
        m_sp = speaker_re.match(line)
        m_h = heading_re.match(line)
        if m_sp and len(m_sp.group(1).split()) <= 3:
            flush()
            current_speaker = m_sp.group(1).strip()
            rest = m_sp.group(2).strip()
            if rest:
                current_lines.append(rest)
        elif m_h:
            flush()
            current_speaker = (m_h.group(1).strip("# :").strip() or "Note")[:40]
            rest = m_h.group(2).strip() if len(m_h.groups()) >= 2 else ""
            if rest:
                current_lines.append(rest)
        else:
            current_lines.append(line)
    flush()
    if not blocks:
        blocks = [{"speaker": "Note", "body": text.strip()[:2000]}] if text.strip() else []

    # Draft project: first block mentioning build/report/dashboard, else first block
    project_name = "Untitled KT Project"
    project_summary = ""
    for b in blocks:
        m = re.search(r"(dashboard|report|feed|migration|monitor\w*|RWA|CVAR|exposure)[^.]{0,60}", b["body"], re.IGNORECASE)
        if m:
            snippet = b["body"][:120].strip().split("\n")[0]
            project_name = snippet[:60] or project_name
            project_summary = b["body"][:300]
            break
    if not project_summary and blocks:
        project_summary = blocks[0]["body"][:300]
        project_name = blocks[0]["body"][:60].split("\n")[0] or project_name

    draft_entries = []
    for b in blocks:
        title = b["body"][:70].split("\n")[0].strip() or f"{b['speaker']} note"
        kind = "note"
        low = b["body"].lower()
        if "caveat" in low or "issue" in low or "jump" in low or "wrong" in low:
            kind = "caveat"
        elif "refresh" in low or "cut-off" in low or "cutoff" in low or "cadence" in low or "daily" in low:
            kind = "howto"
        elif "metric" in low or "definition" in low or "means" in low or "exposure" in low:
            kind = "definition"
        elif "request" in low or "change" in low or "process" in low or "approve" in low:
            kind = "process"
        draft_entries.append({"title": title[:80], "body": b["body"][:2000],
                              "entry_kind": kind, "suggested_speaker": b["speaker"]})
    return {
        "draft_project": {"name": project_name[:80], "summary": project_summary},
        "draft_entries": draft_entries[:8],
        "suggested_subtopic": None,
    }

@app.post("/ingest/transcript")
def ingest_transcript(body: TranscriptIn):
    if not body.text or not body.text.strip():
        raise HTTPException(400, "empty transcript")
    result = parse_transcript(body.text)
    if body.subtopic_id:
        result["suggested_subtopic"] = body.subtopic_id
    return result

# ---------- Mock Jira (deterministic, offline — no network calls) ----------

@app.get("/jira/ticket/{key}")
def preview_ticket(key: str):
    try:
        return ticket_payload(mock_jira_ticket(key))
    except ValueError:
        raise HTTPException(400, "invalid ticket key")

class JiraIn(BaseModel):
    project_id: Optional[int] = None
    subtopic_id: Optional[int] = None
    ticket_key: str = ""
    ticket_keys: Optional[List[str]] = []
    summary: str = ""
    description: str = ""
    entry_kind: str = "note"
    author: str = ""
    updated_at: Optional[str] = None  # ISO string for source_updated_at

def import_mock_tickets(db, subtopic_id: int, project_id: Optional[int],
                        keys: list, entry_kind: str, author: str) -> dict:
    """One ticket entry (description + labels) plus one entry per consecutive
    worklog, all linked to the project. Returns created ids."""
    out, all_ids = [], []
    for key in keys:
        try:
            t = mock_jira_ticket(key)
        except ValueError:
            raise HTTPException(400, f"invalid ticket key: {key}")
        verified = max([t["updated_at"]] + [w["created"] for w in t["worklogs"]]) + timedelta(hours=1)
        te = Entry(subtopic_id=subtopic_id, project_id=project_id,
                   title=f"[{t['ticket_key']}] {t['summary']}"[:120],
                   body=t["description"] + "\n\nLabels: " + ", ".join(t["labels"]),
                   entry_kind=entry_kind or "note",
                   author=author or t["reporter"], verified_at=verified)
        db.add(te); db.flush()
        db.add(Source(entry_id=te.id, source_type="jira",
                      source_ref=t["ticket_key"], source_updated_at=t["updated_at"]))
        wl_ids = []
        for i, w in enumerate(t["worklogs"]):
            we = Entry(subtopic_id=subtopic_id, project_id=project_id,
                       title=f"[{t['ticket_key']}] worklog — {w['author']} {w['created'].date().isoformat()}"[:120],
                       body=w["text"], entry_kind="note",
                       author=w["author"], verified_at=verified)
            db.add(we); db.flush()
            db.add(Source(entry_id=we.id, source_type="jira",
                          source_ref=f"{t['ticket_key']}#wl{i}", source_updated_at=w["created"]))
            wl_ids.append(we.id)
        db.commit()
        out.append({"ticket_key": t["ticket_key"], "entry_id": te.id, "worklog_entry_ids": wl_ids})
        all_ids += [te.id] + wl_ids
    return {"tickets": out, "entry_ids": all_ids}

@app.post("/ingest/jira")
def ingest_jira(body: JiraIn):
    # body: mock ticket JSON -> creates/updates entries and links them to a project
    keys = [k.strip().upper() for k in (body.ticket_keys or []) if k.strip()]
    if body.ticket_key.strip() and not (body.summary or body.description):
        # bare ticket id(s): fetch from the mock store (description + labels + worklogs)
        keys = [body.ticket_key.strip().upper()] + keys
    db = SessionLocal()
    try:
        subtopic_id = body.subtopic_id
        if body.project_id:
            p = db.query(Project).filter(Project.id == body.project_id).first()
            if not p:
                raise HTTPException(400, "invalid project_id")
            subtopic_id = p.subtopic_id
        if not subtopic_id:
            first_sub = db.query(Subtopic).first()
            if not first_sub:
                raise HTTPException(400, "no subtopics seeded")
            subtopic_id = first_sub.id
        if keys:
            return import_mock_tickets(db, subtopic_id, body.project_id, keys,
                                       body.entry_kind, body.author)
        if not body.summary and not body.description:
            raise HTTPException(400, "give ticket id(s) or a mock ticket summary/description")
        now = datetime.utcnow()
        try:
            src_updated = datetime.fromisoformat(body.updated_at) if body.updated_at else now
        except Exception:
            src_updated = now
        e = Entry(subtopic_id=subtopic_id, project_id=body.project_id,
                  title=body.summary[:120] or "Jira import",
                  body=body.description or body.summary,
                  entry_kind=body.entry_kind or "note",
                  author=body.author or "jira-import",
                  verified_at=now)
        db.add(e); db.flush()
        db.add(Source(entry_id=e.id, source_type="jira",
                      source_ref=body.ticket_key or f"JIRA-{e.id}", source_updated_at=src_updated))
        db.commit()
        return {"entry_id": e.id, "title": e.title}
    finally:
        db.close()

class ApproveIn(BaseModel):
    subtopic_id: int
    project_name: str
    project_summary: str = ""
    project_status: str = "live"
    owner: str = ""
    entries: Optional[List[dict]] = []

@app.post("/ingest/approve")
def approve_drafts(body: ApproveIn):
    """One-click approve: creates project + entries + kt_transcript sources."""
    db = SessionLocal()
    try:
        sub = db.query(Subtopic).filter(Subtopic.id == body.subtopic_id).first()
        if not sub:
            raise HTTPException(400, "invalid subtopic_id")
        if not body.project_name:
            raise HTTPException(400, "project_name required")
        p = Project(name=body.project_name, subtopic_id=body.subtopic_id,
                    summary=body.project_summary, status=body.project_status,
                    owner_name=body.owner or "unknown")
        db.add(p); db.flush()
        if body.owner:
            db.add(ProjectPerson(project_id=p.id, person_name=body.owner, role="owner"))
        created = []
        for en in (body.entries or []):
            now = datetime.utcnow()
            e = Entry(subtopic_id=body.subtopic_id, project_id=p.id,
                      title=(en.get("title") or "KT note")[:120],
                      body=en.get("body", ""), entry_kind=en.get("entry_kind", "note"),
                      author=en.get("author", "") or body.owner or "kt-import",
                      verified_at=now)
            db.add(e); db.flush()
            db.add(Source(entry_id=e.id, source_type="kt_transcript",
                          source_ref="kt-paste", source_updated_at=now))
            created.append(e.id)
        db.commit()
        return {"project_id": p.id, "entry_ids": created}
    finally:
        db.close()
