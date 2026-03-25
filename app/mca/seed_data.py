"""Seed data for known MCA lenders and common shell company names."""

# Well-known MCA companies and their common filing aliases
KNOWN_MCA_LENDERS: list[dict] = [
    {"alias_name": "Yellowstone Capital", "canonical_lender_name": "Yellowstone Capital", "confidence": 1.0, "source": "seed"},
    {"alias_name": "Rapid Capital Funding", "canonical_lender_name": "Rapid Capital Funding", "confidence": 1.0, "source": "seed"},
    {"alias_name": "Pearl Capital", "canonical_lender_name": "Pearl Capital", "confidence": 1.0, "source": "seed"},
    {"alias_name": "Fox Capital Group", "canonical_lender_name": "Fox Capital Group", "confidence": 1.0, "source": "seed"},
    {"alias_name": "Credibly", "canonical_lender_name": "Credibly", "confidence": 1.0, "source": "seed"},
    {"alias_name": "Capytal", "canonical_lender_name": "Capytal", "confidence": 1.0, "source": "seed"},
    {"alias_name": "Libertas Funding", "canonical_lender_name": "Libertas Funding", "confidence": 1.0, "source": "seed"},
    {"alias_name": "Fundbox", "canonical_lender_name": "Fundbox", "confidence": 1.0, "source": "seed"},
    {"alias_name": "OnDeck Capital", "canonical_lender_name": "OnDeck Capital", "confidence": 1.0, "source": "seed"},
    {"alias_name": "National Funding", "canonical_lender_name": "National Funding", "confidence": 1.0, "source": "seed"},
    {"alias_name": "Greenbox Capital", "canonical_lender_name": "Greenbox Capital", "confidence": 1.0, "source": "seed"},
    {"alias_name": "Kalamata Capital", "canonical_lender_name": "Kalamata Capital", "confidence": 1.0, "source": "seed"},
    {"alias_name": "Mantis Funding", "canonical_lender_name": "Mantis Funding", "confidence": 1.0, "source": "seed"},
    {"alias_name": "Bizfi", "canonical_lender_name": "Bizfi", "confidence": 1.0, "source": "seed"},
    {"alias_name": "Merchant Cash Group", "canonical_lender_name": "Merchant Cash Group", "confidence": 1.0, "source": "seed"},
    {"alias_name": "Everest Business Funding", "canonical_lender_name": "Everest Business Funding", "confidence": 1.0, "source": "seed"},
    {"alias_name": "World Business Lenders", "canonical_lender_name": "World Business Lenders", "confidence": 1.0, "source": "seed"},
    {"alias_name": "Behalf", "canonical_lender_name": "Behalf", "confidence": 1.0, "source": "seed"},
    {"alias_name": "BlueVine", "canonical_lender_name": "BlueVine", "confidence": 1.0, "source": "seed"},
    {"alias_name": "Can Capital", "canonical_lender_name": "Can Capital", "confidence": 1.0, "source": "seed"},
]

# Common shell company patterns that file on behalf of MCA lenders
SHELL_COMPANY_PATTERNS: list[str] = [
    "funding solutions",
    "capital advance",
    "merchant funding",
    "business funding",
    "revenue purchase",
    "future receivables",
    "cash advance",
    "working capital",
]

# Collateral description keywords indicating MCA
MCA_COLLATERAL_KEYWORDS: list[str] = [
    "all assets",
    "all accounts receivable",
    "future receipts",
    "future receivables",
    "revenue purchase",
    "all inventory",
    "accounts and proceeds",
]
