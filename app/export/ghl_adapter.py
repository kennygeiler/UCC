"""GoHighLevel adapter — concrete CampaignPlatformAdapter implementation."""

import httpx

from app.compliance.export_guard import require_compliance_cleared
from app.config import Settings
from app.export.adapter import CampaignPlatformAdapter
from app.logging import get_logger

logger = get_logger("ghl_adapter")

GHL_API_BASE = "https://services.leadconnectorhq.com"


class GHLAdapter(CampaignPlatformAdapter):
    """GoHighLevel API v2 integration for lead export and campaign management."""

    def __init__(self) -> None:
        """Initialize with settings from environment."""
        settings = Settings()
        self.api_key = settings.GHL_API_KEY or ""
        self.location_id = settings.GHL_LOCATION_ID or ""
        self.workflow_map = {
            "hot": settings.GHL_WORKFLOW_TIER1 or "",
            "warm": settings.GHL_WORKFLOW_TIER2 or "",
            "cold": settings.GHL_WORKFLOW_TIER3 or "",
        }

    def _headers(self) -> dict:
        """Build authorization headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Version": "2021-07-28",
            "Content-Type": "application/json",
        }

    async def upsert_lead(self, lead_data: dict) -> str:
        """Upsert a contact in GoHighLevel via API v2.

        Args:
            lead_data: Lead fields (phone, email, name, company, tags, custom fields).

        Returns:
            GHL contact ID.
        """
        require_compliance_cleared(lead_data)
        payload = {
            "locationId": self.location_id,
            "phone": lead_data.get("phone"),
            "email": lead_data.get("email"),
            "firstName": lead_data.get("owner_name", "").split()[0] if lead_data.get("owner_name") else "",
            "lastName": " ".join(lead_data.get("owner_name", "").split()[1:]) if lead_data.get("owner_name") else "",
            "companyName": lead_data.get("debtor_name"),
            "tags": [
                f"tier-{lead_data.get('mca_tier') or lead_data.get('tier', 'cold')}"
            ],
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{GHL_API_BASE}/contacts/upsert",
                json=payload,
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()
        contact_id = data.get("contact", {}).get("id", "")
        logger.info("ghl_upsert", contact_id=contact_id, company=lead_data.get("debtor_name"))
        return contact_id

    async def enroll_in_campaign(self, contact_id: str, tier: str) -> bool:
        """Enroll contact in the tier-appropriate GHL workflow.

        Args:
            contact_id: GHL contact ID.
            tier: Lead tier for workflow selection.
        """
        workflow_id = self.workflow_map.get(tier, "")
        if not workflow_id:
            logger.warning("no_workflow", tier=tier)
            return False
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{GHL_API_BASE}/contacts/{contact_id}/workflow/{workflow_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
        logger.info("ghl_enrolled", contact_id=contact_id, tier=tier, workflow=workflow_id)
        return True

    def parse_webhook_payload(self, payload: dict) -> dict:
        """Parse GHL webhook into standard disposition format.

        Args:
            payload: Raw GHL webhook payload.
        """
        return {
            "contact_id": payload.get("contactId", ""),
            "disposition": payload.get("pipelineStage", "unknown"),
            "timestamp": payload.get("dateUpdated", ""),
        }

    async def get_disposition_updates(self, since: str | None = None) -> list[dict]:
        """Fetch recent disposition updates via GHL API.

        Args:
            since: ISO timestamp to fetch updates after.
        """
        # GHL uses webhooks for real-time updates — this is a fallback polling method
        logger.info("ghl_polling_dispositions", since=since)
        return []
