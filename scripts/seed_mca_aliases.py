"""Idempotent seed script for the ``mca_aliases`` table.

Reads :data:`app.mca.seed_data.KNOWN_MCA_LENDERS` and inserts any rows whose
``alias_name`` does not already exist. Safe to run multiple times. Honors the
``DATABASE_URL`` env var (and the rest of the project's settings via the .env
file).

Usage::

    python -m scripts.seed_mca_aliases
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.db import get_session
from app.logging import get_logger
from app.mca.seed_data import KNOWN_MCA_LENDERS
from app.models.mca_alias import MCAlias

logger = get_logger("seed_mca_aliases")


async def seed_mca_aliases() -> tuple[int, int]:
    """Insert any missing MCA aliases.

    Returns:
        ``(inserted, total)`` — the count newly inserted on this run and the
        total alias count present in the table after seeding.
    """
    inserted = 0
    async with get_session() as session:
        existing_rows = await session.execute(select(MCAlias.alias_name))
        existing_names = {row[0] for row in existing_rows.all()}

        for entry in KNOWN_MCA_LENDERS:
            if entry["alias_name"] in existing_names:
                continue
            session.add(MCAlias(**entry))
            inserted += 1

        # Flush within the same session so the count reflects this run.
        await session.flush()
        total = (await session.execute(select(MCAlias))).scalars().all()
        total_count = len(total)

    logger.info(
        "mca_aliases_seeded",
        inserted=inserted,
        total=total_count,
        candidates=len(KNOWN_MCA_LENDERS),
    )
    return inserted, total_count


def main() -> None:
    inserted, total = asyncio.run(seed_mca_aliases())
    print(f"Inserted {inserted} new MCA aliases (total now {total}).")


if __name__ == "__main__":
    main()
