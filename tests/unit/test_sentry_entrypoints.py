"""Sentry init wiring for pipeline, agent, and watchdog (PLAT-08)."""

from pathlib import Path


def test_app_and_agent_main_use_settings_not_env_for_sentry():
    """Pipeline and agent must pass SENTRY_DSN via Settings, not raw os.environ."""
    root = Path(__file__).resolve().parents[2]
    app_main = (root / "app" / "main.py").read_text()
    agent_main = (root / "agent" / "main.py").read_text()
    assert 'os.environ.get("SENTRY_DSN"' not in app_main
    assert 'os.environ.get("SENTRY_DSN"' not in agent_main
    assert "send_default_pii=False" in app_main
    assert "send_default_pii=False" in agent_main


def test_watchdog_sentry_reads_env_only():
    """Watchdog reads SENTRY_DSN from environment (C-07)."""
    root = Path(__file__).resolve().parents[2]
    text = (root / "watchdog" / "main.py").read_text()
    assert 'os.environ.get("SENTRY_DSN"' in text
    assert "send_default_pii=False" in text
