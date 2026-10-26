"""Country-aware phone number parser and normalization engine.
Uses Google's libphonenumber (via phonenumbers) to generate standardized
representations, identify carrier metadata, line types, and query variants.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
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
    search_queries: List[str] = field(default_factory=list)


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


def parse_and_normalize(raw_phone: str, default_region: str = "US") -> NormalizedPhone:
    """Parses and normalizes a phone number into all international, national,
    and formatted variants without any network requests.
    """
    raw_clean = raw_phone.strip()
    hmac_id = compute_phone_hmac(raw_clean)
    masked = mask_phone_number(raw_clean)
    
    try:
        parsed_obj = phonenumbers.parse(raw_clean, default_region)
    except phonenumbers.NumberParseException as e:
        # Gracefully handle unparseable inputs
        return NormalizedPhone(
            raw_input=raw_clean,
            is_valid=False,
            is_possible=False,
            e164="",
            international="",
            national="",
            digits_only="".join(c for c in raw_clean if c.isdigit()),
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
        )
    
    is_possible = phonenumbers.is_possible_number(parsed_obj)
    is_valid = phonenumbers.is_valid_number(parsed_obj)
    
    e164 = phonenumbers.format_number(parsed_obj, phonenumbers.PhoneNumberFormat.E164)
    international = phonenumbers.format_number(parsed_obj, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    national = phonenumbers.format_number(parsed_obj, phonenumbers.PhoneNumberFormat.NATIONAL)
    rfc3966 = phonenumbers.format_number(parsed_obj, phonenumbers.PhoneNumberFormat.RFC3966)
    
    # Extract raw national number digits
    national_digits = str(parsed_obj.national_number)
    digits_only = f"{parsed_obj.country_code}{national_digits}"
    
    # Generate variations
    if len(national_digits) == 10:
        dashed = f"{national_digits[:3]}-{national_digits[3:6]}-{national_digits[6:]}"
        dotted = f"{national_digits[:3]}.{national_digits[3:6]}.{national_digits[6:]}"
        spaced = f"{national_digits[:3]} {national_digits[3:6]} {national_digits[6:]}"
    elif len(national_digits) == 9:
        dashed = f"{national_digits[:3]}-{national_digits[3:6]}-{national_digits[6:]}"
        dotted = f"{national_digits[:3]}.{national_digits[3:6]}.{national_digits[6:]}"
        spaced = f"{national_digits[:3]} {national_digits[3:6]} {national_digits[6:]}"
    else:
        dashed = national.replace(" ", "-").replace("(", "").replace(")", "")
        dotted = national.replace(" ", ".").replace("(", "").replace(")", "")
        spaced = national.replace("-", " ").replace("(", "").replace(")", "")
        
    country_code = parsed_obj.country_code
    region_code = phonenumbers.region_code_for_number(parsed_obj) or default_region
    
    # Geographical description and carrier
    location_desc = geocoder.description_for_number(parsed_obj, "en") or ""
    carrier_name = carrier.name_for_number(parsed_obj, "en") or ""
    
    p_type = phonenumbers.number_type(parsed_obj)
    line_type = LINE_TYPE_MAP.get(p_type, "UNKNOWN")
    
    # Re-compute HMAC and masked display based on canonical E.164
    canonical_hmac = compute_phone_hmac(e164)
    canonical_masked = mask_phone_number(e164)
    
    # Generate search query variants for web dorking
    search_queries = list(dict.fromkeys([
        f'"{e164}"',
        f'"{national}"',
        f'"{dashed}"',
        f'"{dotted}"',
        f'"{spaced}"',
        f'"{international}"',
    ]))
    
    return NormalizedPhone(
        raw_input=raw_clean,
        is_valid=is_valid,
        is_possible=is_possible,
        e164=e164,
        international=international,
        national=national,
        digits_only=digits_only,
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
        search_queries=search_queries,
    )
