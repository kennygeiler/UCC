"""GHL webhook receiver for disposition feedback."""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException, Request

from app.compliance.internal_dnc import add_to_dnc
from app.config import Settings
from app.db import get_session
from app.logging import get_logger
from app.models.lead import Lead

logger = get_logger("webhook")

router = APIRouter()


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify GHL webhook signature.

    Args:
        payload: Raw request body.
        signature: Signature from header.
        secret: Webhook secret for HMAC.
    """
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhooks/ghl")
async def handle_ghl_webhook(
    request: Request,
    x_ghl_signature: str = Header(default=""),
):
    """Handle incoming GHL disposition webhooks.

    Verifies signature, maps disposition, updates lead, handles DNC.
    """
    body = await request.body()
    settings = Settings()
    if settings.GHL_WEBHOOK_SECRET:
        if not verify_webhook_signature(body, x_ghl_signature, settings.GHL_WEBHOOK_SECRET):
            raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    await _process_disposition(payload)
    return {"status": "received"}


async def _process_disposition(payload: dict) -> None:
    """Process a disposition update from GHL.

    Args:
        payload: Parsed webhook payload.
    """
    contact_id = payload.get("contactId", "")
    stage = payload.get("pipelineStage", "")
    disposition = _map_disposition(stage)

    async with get_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(Lead).where(Lead.ghl_contact_id == contact_id).limit(1)
        )
        lead = result.scalar_one_or_none()
        if not lead:
            logger.warning("webhook_unknown_contact", contact_id=contact_id)
            return
        lead.disposition = disposition
        lead.disposition_updated_at = datetime.now(timezone.utc)
        session.add(lead)

    if disposition == "dnc":
        await add_to_dnc(phone=lead.phone, email=lead.email, source_channel="ghl_webhook")

    logger.info("disposition_updated", lead_id=lead.id, disposition=disposition)


def _map_disposition(ghl_stage: str) -> str:
    """Map GHL pipeline stage to internal disposition code.

    Args:
        ghl_stage: GHL pipeline stage name.
    """
    mapping = {
        "won": "won",
        "lost": "lost",
        "not_interested": "not_interested",
        "dnc": "dnc",
        "callback": "callback",
        "no_answer": "no_answer",
    }
    return mapping.get(ghl_stage.lower(), ghl_stage.lower())
