"""Unit test: new alias classifies secured party as mca_funder."""

from app.consolidation.classifier import classify_secured_party_name
from app.mca.names import normalize_name


def test_new_alias_classifies_as_mca_funder():
    """Adding an alias to the map should tag the secured party as mca_funder."""
    alias_map = {
        normalize_name("New Test Funder LLC"): "mca_funder",
    }
    assert (
        classify_secured_party_name("New Test Funder LLC", alias_map=alias_map)
        == "mca_funder"
    )
