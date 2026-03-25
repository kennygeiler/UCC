"""Tests for app.db — engine and session factory creation."""


def test_engine_creation_does_not_raise():
    """The async engine should be created without error given a valid URL format."""
    from app.db import get_engine
    engine = get_engine()
    assert engine is not None
    assert "asyncpg" in str(engine.url.drivername)


def test_async_session_factory_exists():
    """The async session factory should be importable."""
    from app.db import get_async_session_factory
    factory = get_async_session_factory()
    assert factory is not None


def test_get_session_is_callable():
    """get_session should be an async context manager."""
    from app.db import get_session
    assert callable(get_session)


def test_dispose_engine_is_callable():
    """dispose_engine should be an async callable."""
    import asyncio
    from app.db import dispose_engine
    assert asyncio.iscoroutinefunction(dispose_engine)
