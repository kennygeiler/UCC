"""Tests for the watchdog service entry point."""

import ast
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from watchdog.main import app


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok():
    """Health endpoint returns 200 with status ok."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_watchdog_has_no_app_or_agent_imports():
    """Verify watchdog/main.py has zero imports from app/ or agent/ (C-07)."""
    watchdog_path = Path(__file__).parents[2] / "watchdog" / "main.py"
    tree = ast.parse(watchdog_path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(("app.", "app", "agent.", "agent")), (
                    f"watchdog/main.py imports {alias.name} — violates C-07"
                )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert not node.module.startswith(("app.", "app", "agent.", "agent")), (
                    f"watchdog/main.py imports from {node.module} — violates C-07"
                )
