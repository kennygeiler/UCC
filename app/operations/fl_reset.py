"""Florida-scoped database reset — thin wrapper over :mod:`app.operations.state_reset`."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.operations.state_reset import ResetCounts, count_state_scoped_rows, reset_state_data

FL_STATE = "FL"

# Backwards-compatible re-exports
__all__ = ["FL_STATE", "ResetCounts", "count_fl_scoped_rows", "reset_fl_data"]


async def count_fl_scoped_rows(session: AsyncSession) -> ResetCounts:
    """Count rows that would be removed by :func:`reset_fl_data`."""
    return await count_state_scoped_rows(session, FL_STATE)


async def reset_fl_data(*, dry_run: bool = False) -> ResetCounts:
    """Clear Florida pipeline data in FK-safe order."""
    return await reset_state_data(FL_STATE, dry_run=dry_run)
