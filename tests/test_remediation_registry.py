"""Tests for the Remediation Source Registry and domain lookup."""

import pytest
from backend.app.engines.remediation.registry import lookup_source_by_url, get_all_sources


@pytest.mark.parametrize("target_url,expected_source_id", [
    ("https://www.fastpeoplesearch.com/person/jane-doe", "fastpeoplesearch"),
    ("https://truepeoplesearch.com/find/person/123", "truepeoplesearch"),
    ("https://www.whitepages.com/name/John-Smith/NY/10001", "whitepages"),
    ("https://radaris.com/p/Bob/Smith", "radaris"),
    ("https://spokeo.com/John-Doe", "spokeo"),
    ("https://nuwber.com/person/5551234", "nuwber"),
    ("https://github.com/myorg/myrepo/blob/main/app.py", "github"),
    ("https://pastebin.com/raw/x82kL90", "pastebin"),
])
def test_remediation_source_domain_lookup(target_url, expected_source_id):
    source = lookup_source_by_url(target_url)
    assert source is not None
    assert source.source_id == expected_source_id
    assert source.official_removal_url.startswith("https://")
    assert len(source.instructions) >= 2


def test_registry_contains_minimum_sources():
    sources = get_all_sources()
    assert len(sources) >= 15
