from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class Topic(Base):
    __tablename__ = "topics"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")

class Subtopic(Base):
    __tablename__ = "subtopics"
    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    name = Column(String, nullable=False)

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    subtopic_id = Column(Integer, ForeignKey("subtopics.id"), nullable=False)
    summary = Column(Text, default="")
    status = Column(String, default="live")  # ongoing | live | deprecated
    owner_name = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class ProjectComponent(Base):
    __tablename__ = "project_components"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    kind = Column(String, default="other")  # api | database | repo | dashboard | report | doc | other
    label = Column(String, default="")
    ref = Column(String, default="")
    notes = Column(Text, default="")

class ProjectPerson(Base):
    __tablename__ = "project_people"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    person_name = Column(String, nullable=False)
    role = Column(String, default="contributor")  # owner | contributor

class Attribute(Base):
    __tablename__ = "attributes"
    id = Column(Integer, primary_key=True)
    owner_type = Column(String, nullable=False)  # project | entry
    owner_id = Column(Integer, nullable=False)
    key = Column(String, nullable=False)
    value = Column(Text, default="")

class Entry(Base):
    __tablename__ = "entries"
    id = Column(Integer, primary_key=True)
    subtopic_id = Column(Integer, ForeignKey("subtopics.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    title = Column(String, nullable=False)
    body = Column(Text, default="")
    entry_kind = Column(String, default="note")  # definition | caveat | howto | process | note
    author = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    verified_at = Column(DateTime, default=datetime.utcnow)

class Source(Base):
    __tablename__ = "sources"
    id = Column(Integer, primary_key=True)
    entry_id = Column(Integer, ForeignKey("entries.id"), nullable=False)
    source_type = Column(String, default="manual")  # kt_transcript | jira | repo | manual
    source_ref = Column(String, default="")
    source_updated_at = Column(DateTime, default=datetime.utcnow)

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    entry_id = Column(Integer, ForeignKey("entries.id"), nullable=True)
    filename = Column(String, nullable=False)  # original filename
    stored_name = Column(String, nullable=False)  # on-disk name under uploads/
    content_type = Column(String, default="")
    size_bytes = Column(Integer, default=0)
    uploaded_by = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

DB_URL = "sqlite:///./knowledge.db"
