"""Internal DNC append-only and reversal (C-12)."""

from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import pytest

from app.models.dnc import DncReversalAudit, InternalDNC


@pytest.mark.asyncio
async def test_reverse_dnc_block_soft_deletes_and_audits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reversal sets is_active False and appends DncReversalAudit (no DELETE)."""
    row = MagicMock(spec=InternalDNC)
    row.id = 42
    row.is_active = True
    added: list = []

    @asynccontextmanager
    async def fake_get_session():
        class Session:
            async def get(self, model, pk):
                if model is InternalDNC and pk == 42:
                    return row
                return None

            def add(self, obj) -> None:
                added.append(obj)

            async def commit(self) -> None:
                return None

            async def rollback(self) -> None:
                return None

            async def close(self) -> None:
                return None

        yield Session()

    monkeypatch.setattr(
        "app.compliance.internal_dnc.get_session",
        fake_get_session,
    )

    from app.compliance.internal_dnc import reverse_dnc_block

    ok = await reverse_dnc_block(42, "mgr@example.com", "customer request")
    assert ok is True
    assert row.is_active is False
    assert len(added) == 1
    assert isinstance(added[0], DncReversalAudit)
    assert added[0].internal_dnc_id == 42
    assert added[0].reversed_by == "mgr@example.com"


@pytest.mark.asyncio
async def test_reverse_dnc_block_idempotent_when_inactive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Second reversal on same id returns False."""
    row = MagicMock(spec=InternalDNC)
    row.id = 7
    row.is_active = False

    @asynccontextmanager
    async def fake_get_session():
        class Session:
            async def get(self, model, pk):
                if model is InternalDNC and pk == 7:
                    return row
                return None

            def add(self, _obj) -> None:
                pass

            async def commit(self) -> None:
                return None

            async def rollback(self) -> None:
                return None

            async def close(self) -> None:
                return None

        yield Session()

    monkeypatch.setattr(
        "app.compliance.internal_dnc.get_session",
        fake_get_session,
    )

    from app.compliance.internal_dnc import reverse_dnc_block

    ok = await reverse_dnc_block(7, "mgr", None)
    assert ok is False
