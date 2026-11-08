"""Async engine, sessions and the job queue."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from windowsticker.db.models import Base, EventRow, TestRow
from windowsticker.domain import utcnow


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        self.engine = create_async_engine(url, pool_pre_ping=True)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.is_postgres = url.startswith("postgresql")

    async def create_all(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(_add_missing_columns)

    async def dispose(self) -> None:
        await self.engine.dispose()

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.sessions() as s:
            yield s

    async def add_event(
        self, test_id: str, kind: str, payload: dict[str, Any], run_id: str | None = None
    ) -> int:
        async with self.session() as s:
            row = EventRow(test_id=test_id, run_id=run_id, kind=kind, payload=payload)
            s.add(row)
            await s.commit()
            return row.id

    async def claim_test(
        self, worker: str, *, only_label: str | None = None, skip_label: str | None = None
    ) -> TestRow | None:
        """Atomically take the oldest queued test, optionally only (or never) tests with a given
        label. Safe with many workers on Postgres."""
        async with self.session() as s:
            q = select(TestRow).where(TestRow.status == "queued")
            if only_label is not None:
                q = q.where(TestRow.label == only_label)
            if skip_label is not None:
                q = q.where(TestRow.label != skip_label)
            q = q.order_by(TestRow.created_at).limit(1)
            if self.is_postgres:
                q = q.with_for_update(skip_locked=True)
            row = (await s.execute(q)).scalar_one_or_none()
            if row is None:
                return None
            res = await s.execute(
                update(TestRow)
                .where(TestRow.id == row.id, TestRow.status == "queued")
                .values(status="running", worker=worker, started_at=utcnow())
            )
            await s.commit()
            if res.rowcount != 1:  # type: ignore[attr-defined]
                return None
            await s.refresh(row)
            return row


def _add_missing_columns(conn: Any) -> None:
    """Additive migrations: columns added after a table was first created. Idempotent."""
    from sqlalchemy import inspect, text

    have = {c["name"] for c in inspect(conn).get_columns("tests")}
    if "environment" not in have:
        conn.execute(
            text("ALTER TABLE tests ADD COLUMN environment VARCHAR(32) NOT NULL DEFAULT 'debian'")
        )
