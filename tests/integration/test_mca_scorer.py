"""Integration tests for MCA scorer DB paths (state-scoped counts)."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, text

from app.db import get_engine, get_session
from app.mca.scorer import count_positions, score_lead
from app.models.filing import UCCFiling

pytestmark = pytest.mark.integration


@pytest.fixture
async def require_postgres():
    """Skip when Postgres is not reachable."""
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
    except OSError as exc:
        pytest.skip(f"Postgres not reachable: {exc}")
    except Exception as exc:
        pytest.skip(f"Postgres unavailable: {exc}")


@pytest.mark.asyncio
@pytest.mark.usefixtures("require_postgres")
async def test_count_positions_filters_by_state():
    """Same debtor in two states: counts are per-state (MCA-02)."""
    debtor = f"Acme Co {uuid.uuid4().hex[:8]}"
    fn1 = f"ST-{uuid.uuid4().hex[:10]}"
    fn2 = f"ST-{uuid.uuid4().hex[:10]}"
    fn3 = f"ST-{uuid.uuid4().hex[:10]}"
    ids: list[int] = []

    async with get_session() as session:
        for fn, st in ((fn1, "TX"), (fn2, "TX"), (fn3, "CA")):
            f = UCCFiling(
                filing_number=fn,
                state=st,
                debtor_name=debtor,
                secured_party=None,
                filing_date=datetime.now(timezone.utc),
                collateral_description=None,
            )
            session.add(f)
            await session.flush()
            ids.append(f.id)

    tx_count = await count_positions(debtor, "TX")
    ca_count = await count_positions(debtor, "CA")
    assert tx_count == 2
    assert ca_count == 1

    async with get_session() as session:
        await session.execute(delete(UCCFiling).where(UCCFiling.id.in_(ids)))


@pytest.mark.asyncio
@pytest.mark.usefixtures("require_postgres")
async def test_score_lead_async_path():
    """await score_lead returns tier and score for seeded filings."""
    debtor = f"Score Test {uuid.uuid4().hex[:8]}"
    fn = f"SC-{uuid.uuid4().hex[:10]}"
    ids: list[int] = []

    async with get_session() as session:
        f = UCCFiling(
            filing_number=fn,
            state="FL",
            debtor_name=debtor,
            secured_party=None,
            filing_date=datetime.now(timezone.utc),
            collateral_description=None,
        )
        session.add(f)
        await session.flush()
        ids.append(f.id)

    out = await score_lead(
        debtor,
        "FL",
        datetime.now(timezone.utc),
        has_mca_collateral=False,
    )
    assert out["tier"] == "cold"
    assert out["mca_position_count"] == 1
    assert "lead_score" in out

    async with get_session() as session:
        await session.execute(delete(UCCFiling).where(UCCFiling.id.in_(ids)))
