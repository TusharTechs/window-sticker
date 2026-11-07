"""Persistence: tests, runs, the event stream and human labels.

JSON columns hold the full evidence and verdict for each run so any run can be replayed
or re-graded later. The schema works on Postgres in production and SQLite in tests.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from windowsticker.domain import utcnow


class Base(DeclarativeBase):
    pass


class TestRow(Base):
    __tablename__ = "tests"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), index=True, default="queued")
    # queued -> running -> finished | failed | cancelled
    agent: Mapped[dict[str, Any]] = mapped_column(JSON)
    agent_name: Mapped[str] = mapped_column(String(200))
    agent_fingerprint: Mapped[str] = mapped_column(String(16), index=True)
    model: Mapped[str] = mapped_column(String(100), index=True)
    suite: Mapped[str] = mapped_column(String(32), default="v1")
    suite_digest: Mapped[str] = mapped_column(String(32), default="")
    runs_requested: Mapped[int] = mapped_column(Integer)
    scenarios: Mapped[list[Any]] = mapped_column(JSON, default=list)
    concurrency: Mapped[int] = mapped_column(Integer, default=8)
    label: Mapped[str] = mapped_column(String(200), default="")  # e.g. "guardrail A/B: B"
    precomputed: Mapped[bool] = mapped_column(Boolean, default=False)  # shown as such in the UI
    worker: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sticker: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class RunRow(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    test_id: Mapped[str] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"), index=True)
    scenario_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), default="finished")
    host_id: Mapped[str] = mapped_column(String(100), default="")
    sandbox_name: Mapped[str] = mapped_column(String(100), default="")
    incident: Mapped[bool] = mapped_column(Boolean, default=False)
    serious: Mapped[bool] = mapped_column(Boolean, default=False)
    task_success: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_label: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    failure_mode: Mapped[str] = mapped_column(String(32), default="none")
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    boot_s: Mapped[float] = mapped_column(Float, default=0.0)
    total_s: Mapped[float] = mapped_column(Float, default=0.0)
    teardown_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    graded: Mapped[bool] = mapped_column(Boolean, default=True)
    record: Mapped[dict[str, Any]] = mapped_column(JSON)  # full evidence + verdict
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EventRow(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_id: Mapped[str] = mapped_column(String(32), index=True)
    run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    kind: Mapped[str] = mapped_column(String(48))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LabelRow(Base):
    __tablename__ = "labels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    incident: Mapped[bool] = mapped_column(Boolean)
    labeller: Mapped[str] = mapped_column(String(100))
    note: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
