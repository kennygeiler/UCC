"""Integration tests for MCA pipeline idempotency and canonical fields."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, text

from app.db import get_engine, get_session
from app.mca.detector import normalize_name
from app.mca.pipeline import get_unprocessed_filings, process_filing
from app.models.filing import UCCFiling
from app.models.lead import Lead

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
async def test_process_filing_idempotent_and_canonical_fields():
    """One lead per filing; second call returns same row; normalized debtor stored."""
    fn = f"PL-{uuid.uuid4().hex[:10]}"
    debtor = f"Pipeline Debtor {uuid.uuid4().hex[:6]}"

    async with get_session() as session:
        f = UCCFiling(
            filing_number=fn,
            state="TX",
            debtor_name=debtor,
            secured_party="ABC Cash Advance Group",
            filing_date=datetime.now(timezone.utc),
            collateral_description=None,
        )
        session.add(f)
        await session.flush()
        fid = f.id

    async with get_session() as session:
        filing = await session.get(UCCFiling, fid)

    lead1 = await process_filing(filing)
    assert lead1 is not None
    assert lead1.source_filing_id == fid
    assert lead1.debtor_name_normalized == normalize_name(debtor)
    assert lead1.mca_tier in ("hot", "warm", "cold")

    lead2 = await process_filing(filing)
    assert lead2.id == lead1.id

    async with get_session() as session:
        await session.execute(delete(Lead).where(Lead.source_filing_id == fid))
        await session.execute(delete(UCCFiling).where(UCCFiling.id == fid))


@pytest.mark.asyncio
@pytest.mark.usefixtures("require_postgres")
async def test_get_unprocessed_filings_uses_filing_not_debtor_name():
    """Two filings same debtor different states both appear when unprocessed."""
    debtor = f"Dup {uuid.uuid4().hex[:8]}"
    fn1 = f"DU-{uuid.uuid4().hex[:10]}"
    fn2 = f"DU-{uuid.uuid4().hex[:10]}"
    ids: list[int] = []

    async with get_session() as session:
        for st, fn in (("TX", fn1), ("CA", fn2)):
            f = UCCFiling(
                filing_number=fn,
                state=st,
                debtor_name=debtor,
                secured_party="ABC Cash Advance Group",
                filing_date=datetime.now(timezone.utc),
                collateral_description=None,
            )
            session.add(f)
            await session.flush()
            ids.append(f.id)

    batch = await get_unprocessed_filings(batch_size=10_000)
    id_set = {f.id for f in batch}
    assert ids[0] in id_set and ids[1] in id_set

    async with get_session() as session:
        await session.execute(delete(UCCFiling).where(UCCFiling.id.in_(ids)))
