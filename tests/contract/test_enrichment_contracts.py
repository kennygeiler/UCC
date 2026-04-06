"""Contract tests — fixture JSON shapes for enrichment normalizers."""

import json
from pathlib import Path

from app.enrichment.normalize import normalize_vendor_response

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "enrichment"


def _load(name: str) -> dict:
    with open(FIXTURES / name, encoding="utf-8") as f:
        return json.load(f)


def test_pdl_fixture_contract():
    raw = _load("pdl_sample.json")
    out = normalize_vendor_response("pdl", raw)
    assert set(out.keys()) == {"phone", "email", "owner_name", "estimated_revenue"}
    assert out["phone"] == "555-0100"


def test_apollo_fixture_contract():
    raw = _load("apollo_sample.json")
    out = normalize_vendor_response("apollo", raw)
    assert out["email"] == "hello@sample.com"
    assert out["estimated_revenue"] == 75000.0


def test_opencorporates_fixture_contract():
    raw = _load("opencorporates_sample.json")
    out = normalize_vendor_response("opencorporates", raw)
    assert out["owner_name"] == "Fixture Corp"
