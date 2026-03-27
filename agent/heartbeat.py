"""Periodic heartbeat writer for the self-healing agent.

Writes a row to agent_heartbeat every 60 seconds so the watchdog
(staleness threshold >5 min) can detect if the agent process is down.
"""

import asyncio
from datetime import datetime, timezone

HEARTBEAT_INTERVAL_SECONDS = 60


async def heartbeat_loop() -> None:
    """Write heartbeat to DB every 60 seconds, indefinitely."""
    from app.db import get_session
    from app.logging import get_logger
    from app.models.operations import AgentHeartbeat
    from sqlalchemy import select

    log = get_logger("agent_heartbeat")

    while True:
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(AgentHeartbeat)
                    .where(AgentHeartbeat.agent_id == "self-healing")
                    .limit(1)
                )
                hb = result.scalar_one_or_none()
                if hb:
                    hb.last_seen = datetime.now(timezone.utc)
                    hb.status = "alive"
                else:
                    hb = AgentHeartbeat(
                        agent_id="self-healing",
                        last_seen=datetime.now(timezone.utc),
                        status="alive",
                    )
                session.add(hb)
            log.debug("heartbeat_written")
        except Exception as exc:
            log.error("heartbeat_write_failed", error=str(exc))
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
