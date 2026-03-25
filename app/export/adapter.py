"""Platform-agnostic campaign adapter interface (C-06).

Pipeline code imports only this abstract interface, never GHL-specific modules.
"""

from abc import ABC, abstractmethod
from typing import Any


class CampaignPlatformAdapter(ABC):
    """Abstract interface for campaign platform integration.

    Concrete implementations: GHLAdapter, CSVFallbackAdapter.
    Pipeline code must only reference this interface.
    """

    @abstractmethod
    async def upsert_lead(self, lead_data: dict) -> str:
        """Create or update a lead in the campaign platform.

        Args:
            lead_data: Lead fields to upsert.

        Returns:
            Platform-specific contact ID.
        """

    @abstractmethod
    async def enroll_in_campaign(self, contact_id: str, tier: str) -> bool:
        """Enroll a contact in a tiered campaign workflow.

        Args:
            contact_id: Platform-specific contact ID.
            tier: Lead tier ('hot', 'warm', 'cold').

        Returns:
            True if enrollment succeeded.
        """

    @abstractmethod
    def parse_webhook_payload(self, payload: dict) -> dict:
        """Parse an incoming webhook payload into standard disposition format.

        Args:
            payload: Raw webhook payload from the platform.

        Returns:
            Standardized dict with contact_id, disposition, timestamp.
        """

    @abstractmethod
    async def get_disposition_updates(self, since: str | None = None) -> list[dict]:
        """Fetch recent disposition updates from the platform.

        Args:
            since: ISO timestamp to fetch updates after.

        Returns:
            List of disposition update dicts.
        """
