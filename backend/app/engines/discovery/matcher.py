"""Context-aware phone number matcher.
Evaluates textual evidence against normalized phone variants and classifies matches
into EXACT, PROBABLE, WEAK, or FALSE_POSITIVE tiers with sanitized snippets,
truthful confidence explanations, and fine-grained match classifications.
"""

import re
from dataclasses import dataclass
from typing import Optional, Tuple
import html
import unicodedata
from bs4 import BeautifulSoup
from backend.app.engines.discovery.normalizer import NormalizedPhone


@dataclass
class MatchResult:
    matched: bool
    match_type: str  # "EXACT", "PROBABLE", "WEAK", "FALSE_POSITIVE", "NONE"
    confidence: float  # 0.0 to 1.0
    matched_text: str
    snippet: str
    match_classification: str = "INCONCLUSIVE"  # "CONFIRMED_MATCH", "POSSIBLE_MATCH", "INCIDENTAL_MENTION", "INCONCLUSIVE", "FALSE_POSITIVE"
    confidence_explanation: str = ""
    is_example_or_test: bool = False


# Regexes to detect common false positive sequences (dates, UUIDs, ISBNs, tracking numbers, transaction IDs)
DATE_PATTERN = re.compile(r"\b(?:19|20)\d{2}[-/.]\d{2}[-/.]\d{2}\b|\b\d{2}[-/.]\d{2}[-/.]\d{4}\b")
UUID_PATTERN = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
ISBN_PATTERN = re.compile(r"\b(?:978|979)[- ]?\d{1,5}[- ]?\d{1,7}[- ]?\d{1,7}[- ]?\d\b")
TRANSACTION_PATTERN = re.compile(
    r"\b(?:TXN|TX|TRX|INV|INVOICE|ORDER|TRK|TRACKING|ACCT|ACCOUNT|REF|BILL|BATCH)[-:\s#]?\w*\d+\b",
    re.IGNORECASE,
)
EXAMPLE_PATTERN = re.compile(
    r"\b(?:e\.g\.|example|sample|dummy|test|placeholder|mock|specimen)\b",
    re.IGNORECASE,
)
OBVIOUS_TEST_DIGITS = re.compile(
    r"\b(?:1234567890|0123456789|9876543210|0000000000|1111111111|9999999999|(\d)\1{9,11})\b"
)

TELEPHONE_CONTEXT_KEYWORDS = re.compile(
    r"\b(?:tel|telephone|phone|call|contact|mobile|cell|direct|sms|text|whatsapp|helpline|fax|dial)\b",
    re.IGNORECASE,
)


def sanitize_html_to_text(html_content: str) -> str:
    """Safely extracts clean plain text from HTML, stripping all script,
    style, and markup elements, decoding HTML entities, and normalizing
    Unicode characters (NFKC) to prevent evasion and false negatives.
    """
    if not html_content:
        return ""
    # Decode HTML entities (e.g. &#43;1-415-555-2671 -> +1-415-555-2671)
    unescaped = html.unescape(html_content)
    # NFKC normalizes fullwidth characters (e.g. ＋１４１５５５５２６７１ -> +14155552671)
    normalized = unicodedata.normalize("NFKC", unescaped)
    try:
        soup = BeautifulSoup(normalized, "html.parser")
        for tag in soup(["script", "style", "noscript", "header", "footer"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        return re.sub(r"\s+", " ", text)
    except Exception:
        # Fallback regex tag stripping
        clean = re.sub(r"<[^>]+>", " ", normalized)
        return re.sub(r"\s+", " ", clean).strip()


def extract_context_snippet(text: str, match_start: int, match_end: int, window: int = 100) -> str:
    """Extracts a bounded text snippet surrounding the matched index."""
    start = max(0, match_start - window)
    end = min(len(text), match_end + window)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end].strip()}{suffix}"


def is_nanp_reserved_example(phone: NormalizedPhone) -> bool:
    """Checks if the phone belongs to NANP officially reserved fictitious series (555-0100 through 555-0199)."""
    digits = phone.digits_only
    if digits.startswith("1") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) == 10 and digits[3:8] == "55501":
        return True
    return False


def match_phone_in_text(text: str, phone: NormalizedPhone) -> MatchResult:
    """Analyzes a block of plain text or HTML for appearances of the target phone number.
    Returns a MatchResult with classification, confidence score, sanitized snippet,
    truthful confidence explanation, and match classification.
    """
    clean_text = sanitize_html_to_text(text)
    if not clean_text or not phone.is_possible:
        return MatchResult(
            matched=False,
            match_type="NONE",
            confidence=0.0,
            matched_text="",
            snippet="",
            match_classification="INCONCLUSIVE",
            confidence_explanation="No telephone candidate found or phone number is invalid.",
        )

    is_test_number = is_nanp_reserved_example(phone) or bool(OBVIOUS_TEST_DIGITS.search(phone.digits_only or ""))

    # 1. Check for EXACT matches (E.164, strict national, international, dashed, dotted)
    parenthesized_variants = []
    if getattr(phone, "parenthesized", None):
        parenthesized_variants.append(phone.parenthesized)
    if phone.national:
        # Standard parenthesized variants: (011) 2345 6789 or (415) 555-2671
        p_std = re.sub(r"^(\d{2,4})\s+", r"(\g<1>) ", phone.national)
        if p_std != phone.national:
            parenthesized_variants.append(p_std)
        p_nanp = re.sub(r"^(\d{3})[-.\s]", r"(\g<1>) ", phone.national)
        if p_nanp != phone.national:
            parenthesized_variants.append(p_nanp)

    exact_candidates = [
        phone.e164,
        phone.international,
        phone.national,
        phone.dashed,
        phone.dotted,
    ] + parenthesized_variants

    for candidate in exact_candidates:
        if candidate and candidate in clean_text:
            idx = clean_text.find(candidate)
            snippet = extract_context_snippet(clean_text, idx, idx + len(candidate))

            # Verify it is not part of a date, UUID, or transaction code
            if (DATE_PATTERN.search(snippet) and len(candidate) <= 10) or TRANSACTION_PATTERN.search(snippet):
                # Check if the match is specifically inside transaction or date
                match_region = clean_text[max(0, idx - 15) : min(len(clean_text), idx + len(candidate) + 15)]
                if TRANSACTION_PATTERN.search(match_region):
                    return MatchResult(
                        matched=False,
                        match_type="FALSE_POSITIVE",
                        confidence=0.0,
                        matched_text=candidate,
                        snippet=snippet,
                        match_classification="FALSE_POSITIVE",
                        confidence_explanation="Candidate sequence is part of an order, invoice, or transaction identifier.",
                        is_example_or_test=False,
                    )

            has_example_marker = bool(EXAMPLE_PATTERN.search(snippet)) or is_test_number
            if has_example_marker:
                return MatchResult(
                    matched=True,
                    match_type="EXACT",
                    confidence=0.90,
                    matched_text=candidate,
                    snippet=snippet,
                    match_classification="POSSIBLE_MATCH",
                    confidence_explanation="Exact representation matched within a recognized documentation or test example context.",
                    is_example_or_test=True,
                )

            return MatchResult(
                matched=True,
                match_type="EXACT",
                confidence=1.0,
                matched_text=candidate,
                snippet=snippet,
                match_classification="CONFIRMED_MATCH",
                confidence_explanation="Exact canonical representation bounded by non-digit delimiters with verified formatting.",
                is_example_or_test=False,
            )

    # 2. Check for spaced or unpunctuated format
    spaced_candidate = phone.spaced
    if spaced_candidate and spaced_candidate in clean_text:
        idx = clean_text.find(spaced_candidate)
        snippet = extract_context_snippet(clean_text, idx, idx + len(spaced_candidate))
        has_example_marker = bool(EXAMPLE_PATTERN.search(snippet)) or is_test_number
        return MatchResult(
            matched=True,
            match_type="PROBABLE",
            confidence=0.85 if not has_example_marker else 0.70,
            matched_text=spaced_candidate,
            snippet=snippet,
            match_classification="POSSIBLE_MATCH",
            confidence_explanation="Spaced national format matching local telephone numbering plan.",
            is_example_or_test=has_example_marker,
        )

    # 3. Check for digits only sequence bounded by non-digit boundaries
    if phone.digits_only and len(phone.digits_only) >= 10:
        pattern = re.compile(rf"(?<!\d){re.escape(phone.digits_only)}(?!\d)")
        match = pattern.search(clean_text)
        if match:
            idx = match.start()
            snippet = extract_context_snippet(clean_text, idx, match.end())

            # Check false positives
            if UUID_PATTERN.search(snippet) or ISBN_PATTERN.search(snippet) or DATE_PATTERN.search(snippet):
                return MatchResult(
                    matched=False,
                    match_type="FALSE_POSITIVE",
                    confidence=0.0,
                    matched_text=match.group(0),
                    snippet=snippet,
                    match_classification="FALSE_POSITIVE",
                    confidence_explanation="Digit sequence rejected: overlaps with UUID, date, or ISBN structure.",
                )

            # Check transaction pattern
            match_region = clean_text[max(0, idx - 15) : min(len(clean_text), match.end() + 15)]
            if TRANSACTION_PATTERN.search(match_region):
                return MatchResult(
                    matched=False,
                    match_type="FALSE_POSITIVE",
                    confidence=0.0,
                    matched_text=match.group(0),
                    snippet=snippet,
                    match_classification="FALSE_POSITIVE",
                    confidence_explanation="Digit sequence matches transaction ID, invoice code, or tracking prefix.",
                )

            has_tel_context = bool(TELEPHONE_CONTEXT_KEYWORDS.search(snippet))
            has_example_marker = bool(EXAMPLE_PATTERN.search(snippet)) or is_test_number

            if has_tel_context:
                return MatchResult(
                    matched=True,
                    match_type="PROBABLE",
                    confidence=0.80 if not has_example_marker else 0.65,
                    matched_text=match.group(0),
                    snippet=snippet,
                    match_classification="POSSIBLE_MATCH",
                    confidence_explanation="Unformatted 10-digit sequence appearing alongside explicit telephone/contact keywords.",
                    is_example_or_test=has_example_marker,
                )
            else:
                return MatchResult(
                    matched=True,
                    match_type="PROBABLE",
                    confidence=0.75 if not has_example_marker else 0.55,
                    matched_text=match.group(0),
                    snippet=snippet,
                    match_classification="INCIDENTAL_MENTION",
                    confidence_explanation="Continuous digit sequence matching telephone length without explicit contact label.",
                    is_example_or_test=has_example_marker,
                )

    # 4. Weak / Inconclusive match: national digits without country code
    national_digits = phone.digits_only[len(str(phone.country_code)) :] if len(phone.digits_only) > 10 else phone.digits_only
    if national_digits and len(national_digits) >= 10:
        pattern = re.compile(rf"(?<!\d){re.escape(national_digits)}(?!\d)")
        match = pattern.search(clean_text)
        if match:
            idx = match.start()
            snippet = extract_context_snippet(clean_text, idx, match.end())
            # Check false positives
            if TRANSACTION_PATTERN.search(snippet) or UUID_PATTERN.search(snippet):
                return MatchResult(
                    matched=False,
                    match_type="FALSE_POSITIVE",
                    confidence=0.0,
                    matched_text=match.group(0),
                    snippet=snippet,
                    match_classification="FALSE_POSITIVE",
                    confidence_explanation="Local digit fragment identified as transaction ID or UUID segment.",
                )

            return MatchResult(
                matched=True,
                match_type="WEAK",
                confidence=0.45,
                matched_text=match.group(0),
                snippet=snippet,
                match_classification="INCONCLUSIVE",
                confidence_explanation="Ambiguous local digit sequence lacking area code or explicit telephone designation.",
                is_example_or_test=is_test_number,
            )

    return MatchResult(
        matched=False,
        match_type="NONE",
        confidence=0.0,
        matched_text="",
        snippet="",
        match_classification="INCONCLUSIVE",
        confidence_explanation="No matching phone representation detected in provided text.",
    )
