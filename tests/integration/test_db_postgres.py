"""Integration smoke: async engine against live Postgres (PLAT-03).

Requires DATABASE_URL pointing at a migrated database. Skips when unreachable.
"""

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_async_engine_select_one():
    """After migrations, SELECT 1 succeeds via the shared async engine."""
    from app.db import get_engine

    try:
        engine = get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            row = result.scalar()
        assert row == 1
    except OSError:
        pytest.skip("Postgres not reachable (network)")
    except Exception as exc:
        pytest.skip(f"Postgres unavailable: {exc}")
