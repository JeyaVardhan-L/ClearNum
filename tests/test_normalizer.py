"""Tests for phone normalization across 10+ international countries."""

import pytest
from backend.app.engines.discovery.normalizer import parse_and_normalize


@pytest.mark.parametrize("raw_input,region,expected_e164,expected_country_code", [
    # US
    ("+1 415 555 2671", "US", "+14155552671", 1),
    ("(415) 555-2671", "US", "+14155552671", 1),
    ("4155552671", "US", "+14155552671", 1),
    # UK
    ("+44 20 7946 0991", "GB", "+442079460991", 44),
    ("020 7946 0991", "GB", "+442079460991", 44),
    # India
    ("+91 98765 43210", "IN", "+919876543210", 91),
    ("09876543210", "IN", "+919876543210", 91),
    # Germany
    ("+49 30 123456", "DE", "+4930123456", 49),
    # France
    ("+33 1 42 68 55 55", "FR", "+33142685555", 33),
    # Japan
    ("+81 3 3580 3311", "JP", "+81335803311", 81),
    # Australia
    ("+61 2 9374 4000", "AU", "+61293744000", 61),
    # Canada
    ("+1 613 555 0177", "CA", "+16135550177", 1),
    # Brazil
    ("+55 11 98765 4321", "BR", "+5511987654321", 55),
    # Singapore
    ("+65 6789 1234", "SG", "+6567891234", 65),
])
def test_normalization_international_formats(raw_input, region, expected_e164, expected_country_code):
    norm = parse_and_normalize(raw_input, region)
    assert norm.is_possible is True
    assert norm.country_code == expected_country_code
    assert norm.e164 == expected_e164
    assert len(norm.masked_display) > 0
    assert norm.hmac_id != ""
    assert len(norm.search_queries) >= 3


def test_invalid_and_impossible_phone():
    norm = parse_and_normalize("not-a-number", "US")
    assert norm.is_valid is False
    assert norm.is_possible is False
    assert norm.e164 == ""
    assert norm.line_type == "INVALID"


def test_variant_generation():
    norm = parse_and_normalize("+14155552671", "US")
    assert norm.dashed == "415-555-2671"
    assert norm.dotted == "415.555.2671"
    assert norm.spaced == "415 555 2671"
    assert norm.rfc3966 == "tel:+1-415-555-2671"
    assert f'"{norm.e164}"' in norm.search_queries
    assert f'"{norm.dashed}"' in norm.search_queries
    assert f'"{norm.national}"' in norm.search_queries


def test_ambiguous_number_without_region_rejected():
    """National-format numbers without '+' or region context must be flagged ambiguous, never guessed as US."""
    norm = parse_and_normalize("9876543210", default_region=None)
    assert norm.is_ambiguous is True
    assert norm.is_valid is False
    assert norm.is_possible is False
    assert norm.line_type == "AMBIGUOUS"
    assert len(norm.search_queries) == 0


def test_india_number_formats_and_permutations():
    """Verify Indian national and international formatting with explicit IN region context."""
    norm = parse_and_normalize("9876543210", default_region="IN")
    assert norm.is_valid is True
    assert norm.country_code == 91
    assert norm.e164 == "+919876543210"
    assert norm.is_ambiguous is False
    # Check permutations contain E.164 and national
    assert f'"{norm.e164}"' in norm.query_permutations


def test_permutation_capping_and_deduplication():
    """Query permutations must be strictly bounded and deduplicated."""
    norm = parse_and_normalize("+14155552671", "US", max_permutations=5)
    assert len(norm.query_permutations) <= 5
    # Verify strict deduplication
    assert len(norm.query_permutations) == len(set(norm.query_permutations))
