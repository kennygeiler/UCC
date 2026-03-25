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


async def run_watchdog_loop() -> None:
    """Main watchdog loop — check heartbeat every 5 minutes."""
    while True:
        is_alive = await check_heartbeat()
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
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
