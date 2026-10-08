from fastapi import FastAPI, HTTPException, Query, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import os
import re
import shutil
import uuid

from models import Base, Topic, Subtopic, Project, ProjectComponent, ProjectPerson, Attribute, Entry, Source, Document, DB_URL

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
        return {
            "id": p.id, "name": p.name, "summary": p.summary, "status": p.status,
            "owner_name": p.owner_name, "subtopic_id": p.subtopic_id,
            "subtopic_name": sub.name if sub else "",
            "documents": [doc_dict(d) for d in docs],
            "components": [{"id": c.id, "kind": c.kind, "label": c.label, "ref": c.ref, "notes": c.notes} for c in comps],
            "people": [{"person_name": x.person_name, "role": x.role} for x in people],
            "attributes": [{"key": a.key, "value": a.value} for a in attrs],
            "entries": [entry_dict(e, db) for e in linked],
            "related_projects": [{"id": r.id, "name": r.name, "status": r.status} for r in related],
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
        m = re.search(r"(dashboard|report|feed|migration|monitor\w*|RWA|CVA|exposure)[^.]{0,60}", b["body"], re.IGNORECASE)
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

class JiraIn(BaseModel):
    project_id: Optional[int] = None
    subtopic_id: Optional[int] = None
    ticket_key: str = ""
    summary: str = ""
    description: str = ""
    entry_kind: str = "note"
    author: str = ""
    updated_at: Optional[str] = None  # ISO string for source_updated_at

@app.post("/ingest/jira")
def ingest_jira(body: JiraIn):
    # body: mock ticket JSON -> creates/updates entries and links them to a project
    if not body.summary and not body.description:
        raise HTTPException(400, "mock ticket needs summary or description")
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
        try:
            src_updated = datetime.fromisoformat(body.updated_at) if body.updated_at else datetime.utcnow()
        except Exception:
            src_updated = datetime.utcnow()
        e = Entry(subtopic_id=subtopic_id, project_id=body.project_id,
                  title=body.summary[:120] or "Jira import",
                  body=body.description or body.summary,
                  entry_kind=body.entry_kind or "note",
                  author=body.author or "jira-import",
                  verified_at=datetime.utcnow())
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
            e = Entry(subtopic_id=body.subtopic_id, project_id=p.id,
                      title=(en.get("title") or "KT note")[:120],
                      body=en.get("body", ""), entry_kind=en.get("entry_kind", "note"),
                      author=en.get("author", "") or body.owner or "kt-import",
                      verified_at=datetime.utcnow())
            db.add(e); db.flush()
            db.add(Source(entry_id=e.id, source_type="kt_transcript",
                          source_ref="kt-paste", source_updated_at=datetime.utcnow()))
            created.append(e.id)
        db.commit()
        return {"project_id": p.id, "entry_ids": created}
    finally:
        db.close()
