"""Canonical enrichment normalization."""

from app.enrichment.normalize import enrichment_meets_bar, normalize_vendor_response


def test_normalize_pdl_minimal():
    raw = {
        "phone": "555-0100",
        "email": "owner@example.com",
        "name": "Jane Owner",
        "inferred_revenue": 125000.0,
    }
    out = normalize_vendor_response("pdl", raw)
    assert out["phone"] == "555-0100"
    assert out["email"] == "owner@example.com"
    assert out["owner_name"] == "Jane Owner"
    assert out["estimated_revenue"] == 125000.0
    assert enrichment_meets_bar(out)


def test_normalize_apollo_minimal():
    raw = {
        "organization": {
            "name": "Acme LLC",
            "email": "info@acme.com",
            "phone": "555-0200",
            "estimated_annual_revenue": 50000.0,
        }
    }
    out = normalize_vendor_response("apollo", raw)
    assert out["email"] == "info@acme.com"
    assert enrichment_meets_bar(out)


def test_normalize_opencorporates_partial():
    raw = {
        "results": {
            "companies": [{"company": {"name": "Acme LLC"}}],
        }
    }
    out = normalize_vendor_response("opencorporates", raw)
    assert out["owner_name"] == "Acme LLC"
    assert out["phone"] is None
    assert not enrichment_meets_bar(out)
