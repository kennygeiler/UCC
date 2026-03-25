"""CSV fallback export — used when GHL API is unavailable."""

import csv
import io
from datetime import datetime, timezone

from app.export.adapter import CampaignPlatformAdapter
from app.logging import get_logger

logger = get_logger("csv_fallback")


class CSVFallbackAdapter(CampaignPlatformAdapter):
    """CSV export adapter for manual upload to campaign platform."""

    def __init__(self, output_dir: str = "/tmp") -> None:
        """Initialize with output directory path.

        Args:
            output_dir: Directory to write CSV files to.
        """
        self.output_dir = output_dir

    async def upsert_lead(self, lead_data: dict) -> str:
        """Append lead to CSV file instead of API call.

        Args:
            lead_data: Lead fields to export.

        Returns:
            Placeholder contact ID (filename:row).
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        filepath = f"{self.output_dir}/leads_export_{timestamp}.csv"
        row = {
            "phone": lead_data.get("phone", ""),
            "email": lead_data.get("email", ""),
            "first_name": lead_data.get("owner_name", "").split()[0] if lead_data.get("owner_name") else "",
            "last_name": " ".join(lead_data.get("owner_name", "").split()[1:]) if lead_data.get("owner_name") else "",
            "company_name": lead_data.get("debtor_name", ""),
            "tags": f"tier-{lead_data.get('tier', 'cold')}",
        }
        _append_csv(filepath, row)
        logger.info("csv_export", filepath=filepath)
        return f"csv:{filepath}"

    async def enroll_in_campaign(self, contact_id: str, tier: str) -> bool:
        """No-op for CSV fallback — campaigns managed manually."""
        logger.info("csv_enroll_skipped", tier=tier)
        return True

    def parse_webhook_payload(self, payload: dict) -> dict:
        """No-op — CSV fallback has no webhooks."""
        return {}

    async def get_disposition_updates(self, since: str | None = None) -> list[dict]:
        """No-op — CSV fallback has no disposition tracking."""
        return []


def _append_csv(filepath: str, row: dict) -> None:
    """Append a row to a CSV file, creating headers if new.

    Args:
        filepath: Path to the CSV file.
        row: Dict of column:value pairs.
    """
    import os
    file_exists = os.path.exists(filepath)
    with open(filepath, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
