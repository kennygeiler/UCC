"""Heartbeat watchdog — independent deadman switch for the self-healing agent.

ZERO imports from app/ or agent/ (C-07). Reads directly from Postgres
and sends alerts via SendGrid independently.
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Read config directly from environment — no app.config import (C-07)
DATABASE_URL = os.environ.get("DATABASE_URL", "")
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
MANAGER_EMAIL = os.environ.get("MANAGER_EMAIL", "")
SENTRY_DSN = os.environ.get("SENTRY_DSN", "")

HEARTBEAT_STALE_MINUTES = 5
CHECK_INTERVAL_SECONDS = 300  # 5 minutes
ALERT_COOLDOWN_MINUTES = 60
LEAD_FLOW_WINDOW_MINUTES = 30
BUSINESS_HOUR_START = 8   # 8 AM ET
BUSINESS_HOUR_END = 18    # 6 PM ET

_last_alert_time: datetime | None = None


def _make_url(url: str) -> str:
    """Convert postgres:// to postgresql+asyncpg:// if needed."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


async def check_heartbeat() -> bool:
    """Check if the agent heartbeat is fresh.

    Returns:
        True if heartbeat is fresh (agent alive).
    """
    if not DATABASE_URL:
        return False
    engine = create_async_engine(_make_url(DATABASE_URL))
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text("SELECT last_seen FROM agent_heartbeat WHERE agent_id = 'self-healing' LIMIT 1")
            )
            row = result.fetchone()
        if not row or not row[0]:
            return False
        stale_threshold = datetime.now(timezone.utc) - timedelta(minutes=HEARTBEAT_STALE_MINUTES)
        return row[0].replace(tzinfo=timezone.utc) > stale_threshold
    finally:
        await engine.dispose()


async def send_alert(subject: str, body: str) -> bool:
    """Send plain-English email alert to manager via SendGrid.

    Args:
        subject: Email subject line.
        body: Plain text email body.

    Returns:
        True if email sent successfully.
    """
    global _last_alert_time
    now = datetime.now(timezone.utc)

    if _last_alert_time and (now - _last_alert_time) < timedelta(minutes=ALERT_COOLDOWN_MINUTES):
        return False  # Deduplicate alerts

    if not SENDGRID_API_KEY or not MANAGER_EMAIL:
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                json={
                    "personalizations": [{"to": [{"email": MANAGER_EMAIL}]}],
                    "from": {"email": "watchdog@uccbusinessdebt.com"},
                    "subject": subject,
                    "content": [{"type": "text/plain", "value": body}],
                },
                headers={
                    "Authorization": f"Bearer {SENDGRID_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
        _last_alert_time = now
        return True
    except Exception:
        return False


def _is_business_hours() -> bool:
    """Check if current time is within business hours (ET)."""
    from zoneinfo import ZoneInfo
    now_et = datetime.now(ZoneInfo("America/New_York"))
    # Monday=0 .. Friday=4
    if now_et.weekday() > 4:
        return False
    return BUSINESS_HOUR_START <= now_et.hour < BUSINESS_HOUR_END


async def check_lead_flow() -> bool:
    """Check if new leads have been inserted within the expected window.

    Returns:
        True if lead flow is healthy (recent records exist or outside business hours).
    """
    if not _is_business_hours():
        return True  # Don't alert outside business hours

    if not DATABASE_URL:
        return True  # Can't check — don't false-alarm

    engine = create_async_engine(_make_url(DATABASE_URL))
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text(
                    "SELECT COUNT(*) FROM leads "
                    "WHERE created_at >= NOW() - MAKE_INTERVAL(mins => :minutes)"
                ),
                {"minutes": LEAD_FLOW_WINDOW_MINUTES},
            )
            count = result.scalar() or 0
        return count > 0
    except Exception:
        return True  # Table may not exist yet — don't false-alarm
    finally:
        await engine.dispose()


async def run_watchdog_loop() -> None:
    """Main watchdog loop — check heartbeat and lead flow every 5 minutes."""
    from watchdog.logging_config import get_logger

    log = get_logger("watchdog_monitor")
    log.info(
        "watchdog_loop_start",
        status="ok",
        error_type=None,
        context={"phase": "startup"},
    )
    while True:
        is_alive = await check_heartbeat()
        log.info(
            "heartbeat_check",
            status="ok" if is_alive else "stale",
            error_type=None,
            context={"agent_alive": is_alive},
        )
        if not is_alive:
            await send_alert(
                subject="UCC Pipeline Alert: Self-Healing Agent Down",
                body=(
                    "The self-healing agent has not sent a heartbeat in over "
                    f"{HEARTBEAT_STALE_MINUTES} minutes. "
                    "The pipeline may not be monitoring for failures. "
                    "Please check the Railway dashboard for the agent service status."
                ),
            )

        # Lead flow check: stale heartbeat + no recent leads = probable outage
        if not is_alive:
            leads_ok = await check_lead_flow()
            if not leads_ok:
                await send_alert(
                    subject="UCC Pipeline Alert: Lead Flow Stopped",
                    body=(
                        f"No new leads have been recorded in the last {LEAD_FLOW_WINDOW_MINUTES} minutes "
                        "during business hours, and the self-healing agent heartbeat is stale. "
                        "The pipeline may be completely down. "
                        "Please check the Railway dashboard immediately."
                    ),
                )

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
