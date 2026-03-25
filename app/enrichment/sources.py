"""Enrichment source connectors — PDL, Apollo, OpenCorporates, Whitepages, Twilio, SOS."""

import httpx

from app.config import Settings
from app.logging import get_logger

logger = get_logger("enrichment_sources")


async def enrich_pdl(business_name: str, state: str, **kwargs) -> dict:
    """Enrich via People Data Labs API.

    Args:
        business_name: Business name to look up.
        state: State code for location context.
    """
    settings = Settings()
    if not settings.PDL_API_KEY:
        raise ValueError("PDL_API_KEY not configured")
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            "https://api.peopledatalabs.com/v5/company/enrich",
            params={"name": business_name, "location": state},
            headers={"X-Api-Key": settings.PDL_API_KEY},
        )
        resp.raise_for_status()
    return resp.json()


async def enrich_apollo(business_name: str, **kwargs) -> dict:
    """Enrich via Apollo.io API.

    Args:
        business_name: Business name to look up.
    """
    settings = Settings()
    if not settings.APOLLO_API_KEY:
        raise ValueError("APOLLO_API_KEY not configured")
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://api.apollo.io/v1/organizations/enrich",
            json={"domain": None, "name": business_name},
            headers={"X-Api-Key": settings.APOLLO_API_KEY},
        )
        resp.raise_for_status()
    return resp.json()


async def enrich_opencorporates(business_name: str, state: str, **kwargs) -> dict:
    """Enrich via OpenCorporates API.

    Args:
        business_name: Business name to look up.
        state: State code for jurisdiction filtering.
    """
    settings = Settings()
    api_token = settings.OPENCORPORATES_API_KEY or ""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            "https://api.opencorporates.com/v0.4/companies/search",
            params={
                "q": business_name,
                "jurisdiction_code": f"us_{state.lower()}",
                "api_token": api_token,
            },
        )
        resp.raise_for_status()
    return resp.json()


async def enrich_whitepages(business_name: str, state: str, **kwargs) -> dict:
    """Enrich via Whitepages Pro API for phone lookup.

    Args:
        business_name: Business name.
        state: State code.
    """
    settings = Settings()
    if not settings.WHITEPAGES_API_KEY:
        raise ValueError("WHITEPAGES_API_KEY not configured")
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            "https://proapi.whitepages.com/3.0/business",
            params={
                "name": business_name,
                "address.state_code": state,
                "api_key": settings.WHITEPAGES_API_KEY,
            },
        )
        resp.raise_for_status()
    return resp.json()


async def validate_phone_twilio(phone: str, **kwargs) -> dict:
    """Validate and classify a phone number via Twilio Lookup.

    Args:
        phone: Phone number to validate.
    """
    settings = Settings()
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        raise ValueError("Twilio credentials not configured")
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"https://lookups.twilio.com/v2/PhoneNumbers/{phone}",
            params={"Fields": "line_type_intelligence"},
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
        )
        resp.raise_for_status()
    return resp.json()
