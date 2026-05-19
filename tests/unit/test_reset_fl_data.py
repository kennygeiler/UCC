"""Unit tests for Florida data reset."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.operations.fl_reset import ResetCounts, count_fl_scoped_rows, reset_fl_data


def _scalar_result(value: int) -> MagicMock:
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


@pytest.mark.asyncio
async def test_count_fl_scoped_rows_sums_categories() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[_scalar_result(n) for n in (1, 2, 3, 4, 5, 6, 7)]
    )
    counts = await count_fl_scoped_rows(session)
    assert counts == ResetCounts(1, 2, 3, 4, 5, 6, 7)
    assert counts.total == 28


@pytest.mark.asyncio
async def test_reset_fl_data_dry_run_does_not_delete() -> None:
    expected = ResetCounts(leads=10, ucc_filings=74)
    with patch(
        "app.operations.state_reset.get_session",
    ) as mock_get_session:
        session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = session
        with patch(
            "app.operations.state_reset.count_state_scoped_rows",
            AsyncMock(return_value=expected),
        ) as mock_count:
            result = await reset_fl_data(dry_run=True)
    assert result == expected
    mock_count.assert_awaited_once_with(session, "FL")
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_reset_fl_data_deletes_in_order() -> None:
    before = ResetCounts(leads=2, ucc_filings=5)
    with patch("app.operations.state_reset.get_session") as mock_get_session:
        session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = session
        with patch(
            "app.operations.state_reset.count_state_scoped_rows",
            AsyncMock(return_value=before),
        ):
            result = await reset_fl_data(dry_run=False)
    assert result == before
    # Seven FK-safe DELETE statements (compliance → retry → leads → accounts → filings → runs → checkpoints)
    assert session.execute.await_count == 7
