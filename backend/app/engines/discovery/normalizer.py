"""Country-aware phone number parser and normalization engine.
India-first design: defaults to India (+91) with robust support for domestic 10-digit formats,
5+5 mobile splits, leading zero national variants, and DoT telecom circle detection.
"""

from dataclasses import dataclass, field
from typing import List, Optional
import phonenumbers
from phonenumbers import geocoder, carrier, PhoneNumberType
from backend.app.core.security import compute_phone_hmac, mask_phone_number


@dataclass
class NormalizedPhone:
    raw_input: str
    is_valid: bool
    is_possible: bool
    e164: str
    international: str
    national: str
    digits_only: str
    dashed: str
    dotted: str
    spaced: str
    rfc3966: str
    country_code: int
    region_code: str
    location_desc: str
    carrier_name: str
    line_type: str
    masked_display: str
    hmac_id: str
    is_ambiguous: bool = False
    search_queries: List[str] = field(default_factory=list)
    query_permutations: List[str] = field(default_factory=list)


LINE_TYPE_MAP = {
    PhoneNumberType.MOBILE: "MOBILE",
    PhoneNumberType.FIXED_LINE: "FIXED_LINE",
    PhoneNumberType.FIXED_LINE_OR_MOBILE: "FIXED_LINE_OR_MOBILE",
    PhoneNumberType.TOLL_FREE: "TOLL_FREE",
    PhoneNumberType.PREMIUM_RATE: "PREMIUM_RATE",
    PhoneNumberType.SHARED_COST: "SHARED_COST",
    PhoneNumberType.VOIP: "VOIP",
    PhoneNumberType.PERSONAL_NUMBER: "PERSONAL_NUMBER",
    PhoneNumberType.PAGER: "PAGER",
    PhoneNumberType.UAN: "UAN",
    PhoneNumberType.VOICEMAIL: "VOICEMAIL",
    PhoneNumberType.UNKNOWN: "UNKNOWN",
}


def parse_and_normalize(
    raw_phone: str,
    default_region: Optional[str] = "IN",
    max_permutations: int = 8,
) -> NormalizedPhone:
    """Parses and normalizes a phone number into international, national,
    and formatted variants without making any network requests.

    Defaults to India ('IN' / +91).
    Requires explicit region context for numbers lacking an international '+' prefix.
    When default_region is None and no '+' prefix is provided, marks the number as AMBIGUOUS.
    """
    raw_clean = raw_phone.strip()
    hmac_id = compute_phone_hmac(raw_clean)
    masked = mask_phone_number(raw_clean)
    digits_only = "".join(c for c in raw_clean if c.isdigit())

    # Require explicit region context for numbers without '+' prefix
    effective_region = default_region.strip().upper() if default_region else None
    if not raw_clean.startswith("+") and not effective_region:
        return NormalizedPhone(
            raw_input=raw_clean,
            is_valid=False,
            is_possible=False,
            is_ambiguous=True,
            e164="",
            international="",
            national="",
            digits_only=digits_only,
            dashed="",
            dotted="",
            spaced="",
            rfc3966="",
            country_code=0,
            region_code="",
            location_desc="",
            carrier_name="",
            line_type="AMBIGUOUS",
            masked_display=masked,
            hmac_id=hmac_id,
            search_queries=[],
            query_permutations=[],
        )

    try:
        parsed_obj = phonenumbers.parse(raw_clean, effective_region)
    except phonenumbers.NumberParseException:
        return NormalizedPhone(
            raw_input=raw_clean,
            is_valid=False,
            is_possible=False,
            is_ambiguous=False,
            e164="",
            international="",
            national="",
            digits_only=digits_only,
            dashed="",
            dotted="",
            spaced="",
            rfc3966="",
            country_code=0,
            region_code="",
            location_desc="",
            carrier_name="",
            line_type="INVALID",
            masked_display=masked,
            hmac_id=hmac_id,
            search_queries=[],
            query_permutations=[],
        )

    is_possible = phonenumbers.is_possible_number(parsed_obj)
    is_valid = phonenumbers.is_valid_number(parsed_obj)

    e164 = phonenumbers.format_number(parsed_obj, phonenumbers.PhoneNumberFormat.E164) if is_possible else ""
    international = phonenumbers.format_number(parsed_obj, phonenumbers.PhoneNumberFormat.INTERNATIONAL) if is_possible else ""
    national = phonenumbers.format_number(parsed_obj, phonenumbers.PhoneNumberFormat.NATIONAL) if is_possible else ""
    rfc3966 = phonenumbers.format_number(parsed_obj, phonenumbers.PhoneNumberFormat.RFC3966) if is_possible else ""

    national_digits = str(parsed_obj.national_number)
    canonical_digits = f"{parsed_obj.country_code}{national_digits}"

    # Generate standardized punctuation variants
    if parsed_obj.country_code == 91 and len(national_digits) == 10:
        # Standard Indian 5+5 mobile split: 98765 43210
        dashed = f"{national_digits[:5]}-{national_digits[5:]}"
        dotted = f"{national_digits[:5]}.{national_digits[5:]}"
        spaced = f"{national_digits[:5]} {national_digits[5:]}"
        parenthesized = f"({national_digits[:5]}) {national_digits[5:]}"
    elif len(national_digits) == 10:
        dashed = f"{national_digits[:3]}-{national_digits[3:6]}-{national_digits[6:]}"
        dotted = f"{national_digits[:3]}.{national_digits[3:6]}.{national_digits[6:]}"
        spaced = f"{national_digits[:3]} {national_digits[3:6]} {national_digits[6:]}"
        parenthesized = f"({national_digits[:3]}) {national_digits[3:6]}-{national_digits[6:]}"
    elif len(national_digits) == 9:
        dashed = f"{national_digits[:3]}-{national_digits[3:6]}-{national_digits[6:]}"
        dotted = f"{national_digits[:3]}.{national_digits[3:6]}.{national_digits[6:]}"
        spaced = f"{national_digits[:3]} {national_digits[3:6]} {national_digits[6:]}"
        parenthesized = national
    else:
        dashed = national.replace(" ", "-").replace("(", "").replace(")", "")
        dotted = national.replace(" ", ".").replace("(", "").replace(")", "")
        spaced = national.replace("-", " ").replace("(", "").replace(")", "")
        parenthesized = national

    country_code = parsed_obj.country_code
    region_code = phonenumbers.region_code_for_number(parsed_obj) or (effective_region or "")

    location_desc = geocoder.description_for_number(parsed_obj, "en") or ""
    carrier_name = carrier.name_for_number(parsed_obj, "en") or ""

    p_type = phonenumbers.number_type(parsed_obj)
    line_type = LINE_TYPE_MAP.get(p_type, "UNKNOWN")

    canonical_hmac = compute_phone_hmac(e164 or raw_clean)
    canonical_masked = mask_phone_number(e164 or raw_clean)

    # Generate controlled, deduplicated query permutations for search discovery
    if country_code == 91 and len(national_digits) == 10:
        raw_candidates = [
            f'"{e164}"',
            f'"{national_digits}"',
            f'"{spaced}"',
            f'"{dashed}"',
            f'"0{national_digits}"',
            f'"{national}"',
            f'"{international}"',
            f'"{canonical_digits}"',
        ]
    else:
        raw_candidates = [
            f'"{e164}"',
            f'"{national}"',
            f'"{dashed}"',
            f'"{parenthesized}"',
            f'"{spaced}"',
            f'"{dotted}"',
            f'"{international}"',
            f'"{canonical_digits}"',
        ]

    # Deduplicate while preserving rank order
    deduped_queries = []
    seen = set()
    for q in raw_candidates:
        clean_q = q.strip()
        if clean_q and clean_q not in seen and clean_q != '""':
            seen.add(clean_q)
            deduped_queries.append(clean_q)

    # Add bounded contextual dork
    if e164:
        if country_code == 91:
            contextual_dork = f'"{e164}" (site:justdial.com OR site:indiamart.com OR site:zaubacorp.com)'
        else:
            contextual_dork = f'"{e164}" (site:pastebin.com OR site:github.com)'
        if contextual_dork not in seen:
            deduped_queries.append(contextual_dork)

    # Apply maximum permutation cap
    bounded_queries = deduped_queries[:max_permutations]

    return NormalizedPhone(
        raw_input=raw_clean,
        is_valid=is_valid,
        is_possible=is_possible,
        is_ambiguous=False,
        e164=e164,
        international=international,
        national=national,
        digits_only=canonical_digits,
        dashed=dashed,
        dotted=dotted,
        spaced=spaced,
        rfc3966=rfc3966,
        country_code=country_code,
        region_code=region_code,
        location_desc=location_desc,
        carrier_name=carrier_name,
        line_type=line_type,
        masked_display=canonical_masked,
        hmac_id=canonical_hmac,
        search_queries=bounded_queries,
        query_permutations=bounded_queries,
    )
