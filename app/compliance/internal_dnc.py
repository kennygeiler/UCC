"""Internal DNC management — append-only, irrevocable (C-12).

Any DNC request via any channel creates a permanent block.
Reversal requires explicit manager action with audit trail.
"""

from datetime import datetime, timezone

from sqlalchemy import select

from app.db import get_session
from app.logging import get_logger
from app.models.dnc import InternalDNC

logger = get_logger("internal_dnc")


async def add_to_dnc(
    phone: str | None = None,
    email: str | None = None,
    source_channel: str = "manual",
    added_by: str = "system",
) -> bool:
    """Add a phone/email to the internal DNC list. Append-only.

    Args:
        phone: Phone number to block.
        email: Email to block.
        source_channel: How the DNC request came in (sms, call, webhook, manual).
        added_by: Who added it (system, manager, ghl_webhook).

    Returns:
        True if a new entry was created.
    """
    if not phone and not email:
        return False

    async with get_session() as session:
        # Check if already on DNC
        if phone:
            existing = await session.execute(
                select(InternalDNC.id).where(InternalDNC.phone == phone).limit(1)
            )
            if existing.scalar_one_or_none() is not None:
                return False

        entry = InternalDNC(
            phone=phone,
            email=email,
            source_channel=source_channel,
            added_by=added_by,
            added_at=datetime.now(timezone.utc),
        )
        session.add(entry)

    logger.info("dnc_added", phone=phone, email=email, source=source_channel)
    return True


async def is_on_dnc(phone: str | None = None, email: str | None = None) -> bool:
    """Check if a phone or email is on the internal DNC list.

    Args:
        phone: Phone number to check.
        email: Email to check.
    """
    if not phone and not email:
        return False

    async with get_session() as session:
        if phone:
            result = await session.execute(
                select(InternalDNC.id).where(InternalDNC.phone == phone).limit(1)
            )
            if result.scalar_one_or_none() is not None:
                return True
        if email:
            result = await session.execute(
                select(InternalDNC.id).where(InternalDNC.email == email).limit(1)
            )
            if result.scalar_one_or_none() is not None:
                return True
    return False
