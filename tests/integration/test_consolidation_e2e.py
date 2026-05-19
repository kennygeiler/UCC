"""E2E consolidation workflow on local Postgres."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, func, select, text

from app.consolidation.pipeline import run_post_scrape_pipeline
from app.db import get_engine, get_session
from app.models.account import BusinessAccount
from app.models.filing import UCCFiling

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
async def test_post_scrape_pipeline_populates_accounts():
    """Pipeline on existing FL filings creates scored business accounts."""
    tag = uuid.uuid4().hex[:8]
    fn = f"E2E-{tag}"

    async with get_session() as session:
        session.add(
            UCCFiling(
                filing_number=fn,
                state="FL",
                debtor_name=f"E2E Consolidation {tag} LLC",
                secured_party="Yellowstone Capital LLC",
                filing_date=datetime.now(timezone.utc),
                collateral_description="all assets",
                is_mca=True,
            )
        )

    summary = await run_post_scrape_pipeline(state="FL", run_mca=False)
    assert summary["accounts_rolled_up"] >= 0

    async with get_session() as session:
        count = (
            await session.execute(
                select(func.count(BusinessAccount.id)).where(BusinessAccount.state == "FL")
            )
        ).scalar_one()
        account = (
            await session.execute(
                select(BusinessAccount).where(
                    BusinessAccount.display_name.ilike(f"%{tag}%")
                )
            )
        ).scalar_one_or_none()

    assert count >= 1
    assert account is not None
    assert account.consolidation_score is not None
    assert account.consolidation_tier in ("priority", "work", "monitor", "suppress")
    assert account.score_components

    async with get_session() as session:
        await session.execute(delete(UCCFiling).where(UCCFiling.filing_number == fn))
        if account:
            await session.execute(
                delete(BusinessAccount).where(BusinessAccount.id == account.id)
            )
