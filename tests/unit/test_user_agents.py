"""Tests for User-Agent string rotation."""

from app.scrapers.user_agents import USER_AGENTS, get_random_user_agent


def test_user_agents_has_at_least_ten():
    """USER_AGENTS list must contain at least 10 entries."""
    assert len(USER_AGENTS) >= 10


def test_all_user_agents_are_strings():
    """Every entry in USER_AGENTS must be a non-empty string."""
    for ua in USER_AGENTS:
        assert isinstance(ua, str)
        assert len(ua) > 0


def test_get_random_user_agent_returns_valid():
    """get_random_user_agent returns a string from the USER_AGENTS list."""
    ua = get_random_user_agent()
    assert ua in USER_AGENTS


def test_get_random_user_agent_has_variety():
    """Multiple calls should eventually return different values."""
    results = {get_random_user_agent() for _ in range(50)}
    assert len(results) > 1


def test_user_agents_contain_mozilla():
    """All User-Agent strings should contain Mozilla (realistic browser UA)."""
    for ua in USER_AGENTS:
        assert "Mozilla" in ua
