"""Unit tests for compliance gate orchestration (COMPLY-01, COMPLY-04)."""

from contextlib import asynccontextmanager

import pytest

from app.compliance import gate
from app.models.dnc import ComplianceCheck
from app.models.lead import Lead


def _fake_session_factory(leads_by_id: dict, checks: list) -> object:
    """Build an async context manager that mimics ``get_session`` for gate tests."""

    @asynccontextmanager
    async def fake_get_session():
        class Session:
            async def get(self, model, pk):
                if model is Lead:
                    return leads_by_id.get(pk)
                return None

            def add(self, obj):
                if isinstance(obj, ComplianceCheck):
                    checks.append(obj)

            async def commit(self) -> None:
                return None

            async def rollback(self) -> None:
                return None

            async def close(self) -> None:
                return None

        yield Session()

    return fake_get_session


@pytest.fixture
def sample_lead() -> Lead:
    """Detached lead row used with mocked persistence."""
    return Lead(
        id=1,
        debtor_name="Acme LLC",
        debtor_name_normalized="acme llc",
        state="CA",
        phone="5551234567",
        email="owner@acme.test",
    )


@pytest.mark.asyncio
async def test_full_pass_writes_four_compliance_checks(
    monkeypatch: pytest.MonkeyPatch, sample_lead: Lead
) -> None:
    """All four layers pass; four audit rows; lead marked cleared."""
    checks: list[ComplianceCheck] = []
    leads_by_id = {sample_lead.id: sample_lead}
    monkeypatch.setattr(
        "app.compliance.gate.get_session",
        _fake_session_factory(leads_by_id, checks),
    )

    async def pass_fn(*_a, **_k):
        return False

    monkeypatch.setattr("app.compliance.gate.check_internal_dnc", pass_fn)
    monkeypatch.setattr("app.compliance.gate.check_datamerch", pass_fn)
    monkeypatch.setattr("app.compliance.gate.check_dnc_scrub", pass_fn)
    monkeypatch.setattr("app.compliance.gate.check_blacklist_alliance", pass_fn)

    ok = await gate.run_compliance_gate(sample_lead)
    assert ok is True
    assert len(checks) == 4
    assert [c.gate_name for c in checks] == [
        "internal_dnc",
        "datamerch",
        "dnc_scrub",
        "blacklist_alliance",
    ]
    assert all(c.result == "pass" for c in checks)
    assert sample_lead.compliance_status == "cleared"


@pytest.mark.asyncio
async def test_block_on_datamerch_stops_after_two_checks(
    monkeypatch: pytest.MonkeyPatch, sample_lead: Lead
) -> None:
    """First layer passes, second blocks; two ComplianceCheck rows; status set."""
    checks: list[ComplianceCheck] = []
    leads_by_id = {sample_lead.id: sample_lead}
    monkeypatch.setattr(
        "app.compliance.gate.get_session",
        _fake_session_factory(leads_by_id, checks),
    )

    async def internal_ok(*_a, **_k):
        return False

    async def datamerch_blocks(*_a, **_k):
        return True

    monkeypatch.setattr("app.compliance.gate.check_internal_dnc", internal_ok)
    monkeypatch.setattr("app.compliance.gate.check_datamerch", datamerch_blocks)

    ok = await gate.run_compliance_gate(sample_lead)
    assert ok is False
    assert len(checks) == 2
    assert checks[0].gate_name == "internal_dnc" and checks[0].result == "pass"
    assert checks[1].gate_name == "datamerch" and checks[1].result == "blocked"
    assert sample_lead.compliance_status == "blocked:datamerch"


def _ordered_layer(name: str, order: list[str]):
    async def fn(*_a, **_k):
        order.append(name)
        return False

    return fn


@pytest.mark.asyncio
async def test_layer_invocation_order(
    monkeypatch: pytest.MonkeyPatch, sample_lead: Lead
) -> None:
    """Layers run strictly internal_dnc → datamerch → dnc_scrub → blacklist."""
    order: list[str] = []
    checks: list[ComplianceCheck] = []
    leads_by_id = {sample_lead.id: sample_lead}
    monkeypatch.setattr(
        "app.compliance.gate.get_session",
        _fake_session_factory(leads_by_id, checks),
    )

    monkeypatch.setattr(
        "app.compliance.gate.check_internal_dnc",
        _ordered_layer("internal_dnc", order),
    )
    monkeypatch.setattr(
        "app.compliance.gate.check_datamerch",
        _ordered_layer("datamerch", order),
    )
    monkeypatch.setattr(
        "app.compliance.gate.check_dnc_scrub",
        _ordered_layer("dnc_scrub", order),
    )
    monkeypatch.setattr(
        "app.compliance.gate.check_blacklist_alliance",
        _ordered_layer("blacklist_alliance", order),
    )

    await gate.run_compliance_gate(sample_lead)
    assert order == [
        "internal_dnc",
        "datamerch",
        "dnc_scrub",
        "blacklist_alliance",
    ]
