"""Tests for ORM models — verify all 13 model classes are importable and instantiable."""

from datetime import datetime, timezone


def test_all_models_importable():
    """All 13 model classes must be importable from app.models."""
    from app.models import (
        UCCFiling,
        Lead,
        MCAlias,
        InternalDNC,
        EnrichmentCache,
        ComplianceCheck,
        JobQueue,
        EnrichmentRetryQueue,
        StatePriority,
        ScraperRun,
        AgentHeartbeat,
        PipelineEvent,
        LanggraphCheckpoint,
    )
    assert len([
        UCCFiling, Lead, MCAlias, InternalDNC, EnrichmentCache,
        ComplianceCheck, JobQueue, EnrichmentRetryQueue, StatePriority,
        ScraperRun, AgentHeartbeat, PipelineEvent, LanggraphCheckpoint,
    ]) == 13


def test_ucc_filing_instantiation():
    """UCCFiling can be instantiated with valid data."""
    from app.models import UCCFiling
    filing = UCCFiling(
        filing_number="2024-001",
        state="CA",
        debtor_name="Test Corp",
        secured_party="Lender LLC",
    )
    assert filing.filing_number == "2024-001"
    assert filing.state == "CA"


def test_lead_instantiation():
    """Lead can be instantiated with valid data."""
    from app.models import Lead
    lead = Lead(
        debtor_name="Test Corp",
        state="NY",
        lead_score=85.0,
        mca_position_count=3,
    )
    assert lead.debtor_name == "Test Corp"
    assert lead.lead_score == 85.0


def test_mca_alias_instantiation():
    """MCAlias can be instantiated."""
    from app.models import MCAlias
    alias = MCAlias(
        alias_name="Shell Corp LLC",
        canonical_lender_name="Big MCA Lender",
        confidence=0.95,
        source="manual",
    )
    assert alias.alias_name == "Shell Corp LLC"


def test_internal_dnc_instantiation():
    """InternalDNC can be instantiated."""
    from app.models import InternalDNC
    entry = InternalDNC(
        phone="5551234567",
        email="test@example.com",
        source_channel="sms_stop",
        added_by="system",
    )
    assert entry.phone == "5551234567"


def test_enrichment_cache_instantiation():
    """EnrichmentCache can be instantiated."""
    from app.models import EnrichmentCache
    cache = EnrichmentCache(
        source_api="apollo",
        input_key="test-corp-ca",
        result_json={"email": "test@corp.com"},
    )
    assert cache.source_api == "apollo"


def test_compliance_check_instantiation():
    """ComplianceCheck can be instantiated."""
    from app.models import ComplianceCheck
    check = ComplianceCheck(
        lead_id=1,
        gate_name="internal_dnc",
        result="pass",
    )
    assert check.gate_name == "internal_dnc"


def test_job_queue_instantiation():
    """JobQueue can be instantiated with required fields."""
    from app.models import JobQueue
    job = JobQueue(
        job_type="scrape",
        payload={"state": "CA"},
        status="pending",
        retry_count=0,
    )
    assert job.job_type == "scrape"
    assert job.status == "pending"
    assert job.retry_count == 0


def test_enrichment_retry_queue_instantiation():
    """EnrichmentRetryQueue can be instantiated."""
    from app.models import EnrichmentRetryQueue
    retry = EnrichmentRetryQueue(
        lead_id=1,
        source="pdl",
        attempt_count=2,
        last_error="timeout",
    )
    assert retry.source == "pdl"


def test_state_priority_instantiation():
    """StatePriority can be instantiated."""
    from app.models import StatePriority
    sp = StatePriority(state="CA", tier=1, leads_last_30_days=500)
    assert sp.state == "CA"
    assert sp.tier == 1


def test_scraper_run_instantiation():
    """ScraperRun can be instantiated."""
    from app.models import ScraperRun
    now = datetime.now(timezone.utc)
    run = ScraperRun(state="TX", started_at=now, status="running")
    assert run.state == "TX"


def test_agent_heartbeat_instantiation():
    """AgentHeartbeat can be instantiated."""
    from app.models import AgentHeartbeat
    hb = AgentHeartbeat(agent_id="agent-1", status="active")
    assert hb.agent_id == "agent-1"


def test_pipeline_event_instantiation():
    """PipelineEvent can be instantiated."""
    from app.models import PipelineEvent
    event = PipelineEvent(
        event_type="scrape_complete",
        component="scraper",
        detail="CA scraped 150 records",
    )
    assert event.event_type == "scrape_complete"


def test_langgraph_checkpoint_instantiation():
    """LanggraphCheckpoint can be instantiated."""
    from app.models import LanggraphCheckpoint
    cp = LanggraphCheckpoint(
        thread_id="thread-abc",
        checkpoint={"state": "diagnosing"},
        metadata_={"step": 3},
    )
    assert cp.thread_id == "thread-abc"
