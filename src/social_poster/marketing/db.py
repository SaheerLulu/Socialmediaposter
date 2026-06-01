"""SQLAlchemy data model for the CRM database.

Backed by **Postgres** in production (set `DATABASE_URL=postgresql+psycopg://...`)
and any SQLAlchemy-supported engine for local dev/tests (SQLite by default).

Three tables:
  leads            — the contacts themselves
  consent_records  — an append-only audit of lawful-basis evidence (GDPR)
  activities       — an append-only log of every touch / status change

The append-only tables matter: if you ever have to prove *why* you were allowed
to contact someone, or what you sent and when, it's all here.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class LeadRow(Base):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    email: Mapped[str | None] = mapped_column(String(320), index=True, nullable=True)
    whatsapp: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    company: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(255), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    consent: Mapped[str] = mapped_column(String(32), default="none", index=True)
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    source: Mapped[str] = mapped_column(String(128), default="")
    touches: Mapped[int] = mapped_column(Integer, default=0)
    last_contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_followup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    consents: Mapped[list["ConsentRow"]] = relationship(back_populates="lead", cascade="all,delete")
    activities: Mapped[list["ActivityRow"]] = relationship(back_populates="lead", cascade="all,delete")


class ConsentRow(Base):
    __tablename__ = "consent_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    basis: Mapped[str] = mapped_column(String(32))  # opt_in / legitimate_interest / unsubscribed
    source: Mapped[str] = mapped_column(String(255), default="")
    evidence: Mapped[str] = mapped_column(Text, default="")  # e.g. "form submit 2026-01-02, ip ..."
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    lead: Mapped[LeadRow] = relationship(back_populates="consents")


class ActivityRow(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(48))  # imported / sent_email / sent_whatsapp / status / unsubscribe
    channel: Mapped[str] = mapped_column(String(32), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    lead: Mapped[LeadRow] = relationship(back_populates="activities")


# --------------------------------------------------------------------------- #
# Engine / session
# --------------------------------------------------------------------------- #
def database_url() -> str:
    """Resolve the DB URL. Defaults to a local SQLite file when DATABASE_URL is
    unset, so the demo runs with zero infrastructure."""
    url = os.getenv("DATABASE_URL")
    if url:
        # normalize the common "postgres://" form to a driver SQLAlchemy ships with
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        return url
    from .config import DATA_DIR

    return f"sqlite:///{DATA_DIR / 'crm.db'}"


_engine = None
_Session = None


def get_session_factory():
    global _engine, _Session
    if _Session is None:
        _engine = create_engine(database_url(), future=True)
        Base.metadata.create_all(_engine)
        _Session = sessionmaker(bind=_engine, future=True, expire_on_commit=False)
    return _Session


def init_db() -> str:
    """Create all tables. Returns the resolved database URL."""
    get_session_factory()
    return database_url()
