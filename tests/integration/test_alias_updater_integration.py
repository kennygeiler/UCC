"""Integration tests for MCA alias updater idempotency."""

import uuid

import pytest
from sqlalchemy import delete, text

from app.db import get_engine, get_session
from app.mca.alias_updater import run_alias_update
from app.models.mca_alias import MCAlias

pytestmark = pytest.mark.integration


@pytest.fixture
async def require_postgres():
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
    except OSError as exc:
        pytest.skip(f"Postgres not reachable: {exc}")
    except Exception as exc:
        pytest.skip(f"Postgres unavailable: {exc}")


@pytest.mark.asyncio
@pytest.mark.usefixtures("require_postgres")
async def test_run_alias_update_twice_idempotent(monkeypatch):
    """Second run inserts no duplicate rows for same alias_name."""
    unique_name = f"Unique Lender {uuid.uuid4().hex[:12]}"

    async def fake_parties():
        return [unique_name]

    monkeypatch.setattr(
        "app.mca.alias_updater.find_high_converting_parties",
        fake_parties,
    )

    n1 = await run_alias_update()
    n2 = await run_alias_update()
    assert n2 == 0
    assert n1 == 1

    async with get_session() as session:
        await session.execute(delete(MCAlias).where(MCAlias.alias_name == unique_name))
