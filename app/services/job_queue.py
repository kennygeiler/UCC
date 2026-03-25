"""Postgres job queue service using SELECT FOR UPDATE SKIP LOCKED.

Provides enqueue, claim, complete, and fail operations for the job_queue table.
No Redis, no Kafka — pure Postgres queueing per ADR-010.
"""

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import JobQueue


async def enqueue(
    session: AsyncSession,
    job_type: str,
    payload: dict,
    priority: int = 0,
    scheduled_at: datetime | None = None,
) -> int:
    """Create a new pending job in the queue. Returns the job id."""
    job = JobQueue(
        job_type=job_type,
        payload=payload,
        status="pending",
        priority=priority,
        scheduled_at=scheduled_at or datetime.now(timezone.utc),
    )
    session.add(job)
    await session.flush()
    return job.id


async def claim(
    session: AsyncSession,
    job_types: list[str],
    worker_id: str,
) -> JobQueue | None:
    """Claim the highest-priority pending job using SELECT FOR UPDATE SKIP LOCKED.

    Returns the claimed job or None if no jobs are available.
    Only claims jobs where status='pending' and scheduled_at <= now.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        select(JobQueue)
        .where(
            JobQueue.status == "pending",
            JobQueue.job_type.in_(job_types),
            JobQueue.scheduled_at <= now,
        )
        .order_by(JobQueue.priority.desc(), JobQueue.scheduled_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()
    if job is None:
        return None
    job.status = "running"
    job.started_at = now
    await session.flush()
    return job


async def complete(
    session: AsyncSession,
    job_id: int,
    result: dict | None = None,
) -> None:
    """Mark a job as completed."""
    now = datetime.now(timezone.utc)
    stmt = (
        update(JobQueue)
        .where(JobQueue.id == job_id)
        .values(status="completed", completed_at=now)
    )
    await session.execute(stmt)
    await session.flush()


async def fail(
    session: AsyncSession,
    job_id: int,
    error: str,
) -> None:
    """Mark a job as failed and increment retry_count."""
    now = datetime.now(timezone.utc)
    stmt = (
        update(JobQueue)
        .where(JobQueue.id == job_id)
        .values(
            status="failed",
            completed_at=now,
            last_error=error,
            retry_count=JobQueue.retry_count + 1,
        )
    )
    await session.execute(stmt)
    await session.flush()
