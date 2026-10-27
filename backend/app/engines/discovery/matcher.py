"""Context-aware phone number matcher.
Evaluates textual evidence against normalized phone variants and classifies matches
into EXACT, PROBABLE, WEAK, or FALSE_POSITIVE tiers with sanitized snippets.
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
    match_type: str  # "EXACT", "PROBABLE", "WEAK", "FALSE_POSITIVE"
    confidence: float  # 0.0 to 1.0
    matched_text: str
    snippet: str


# Regexes to detect common false positive sequences (dates, UUIDs, ISBNs, tracking numbers)
DATE_PATTERN = re.compile(r"\b(?:19|20)\d{2}[-/.]\d{2}[-/.]\d{2}\b")
UUID_PATTERN = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
ISBN_PATTERN = re.compile(r"\b(?:978|979)[- ]?\d{1,5}[- ]?\d{1,7}[- ]?\d{1,7}[- ]?\d\b")


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


def match_phone_in_text(text: str, phone: NormalizedPhone) -> MatchResult:
    """Analyzes a block of plain text or HTML for appearances of the target phone number.
    Returns a MatchResult with classification, confidence score, and sanitized snippet.
    """
    clean_text = sanitize_html_to_text(text)
    if not clean_text or not phone.is_possible:
        return MatchResult(
            matched=False,
            match_type="NONE",
            confidence=0.0,
            matched_text="",
            snippet="",
        )
    
    # 1. Check for EXACT matches (E.164, strict national, international)
    exact_candidates = [
        phone.e164,
        phone.international,
        phone.national,
        phone.dashed,
        phone.dotted,
    ]
    
    for candidate in exact_candidates:
        if candidate and candidate in clean_text:
            idx = clean_text.find(candidate)
            snippet = extract_context_snippet(clean_text, idx, idx + len(candidate))
            
            # Verify it is not part of a date or UUID
            if DATE_PATTERN.search(snippet) and len(candidate) <= 10:
                # Could be a date false positive
                pass
            else:
                return MatchResult(
                    matched=True,
                    match_type="EXACT",
                    confidence=1.0,
                    matched_text=candidate,
                    snippet=snippet,
                )
    
    # 2. Check for spaced or unpunctuated format
    spaced_candidate = phone.spaced
    if spaced_candidate and spaced_candidate in clean_text:
        idx = clean_text.find(spaced_candidate)
        snippet = extract_context_snippet(clean_text, idx, idx + len(spaced_candidate))
        return MatchResult(
            matched=True,
            match_type="PROBABLE",
            confidence=0.85,
            matched_text=spaced_candidate,
            snippet=snippet,
        )
        
    # 3. Check for digits only sequence bounded by word boundaries
    if phone.digits_only and len(phone.digits_only) >= 10:
        pattern = re.compile(rf"(?<!\d){re.escape(phone.digits_only)}(?!\d)")
        match = pattern.search(clean_text)
        if match:
            idx = match.start()
            snippet = extract_context_snippet(clean_text, idx, match.end())
            # Check false positives
            if UUID_PATTERN.search(snippet) or ISBN_PATTERN.search(snippet):
                return MatchResult(
                    matched=False,
                    match_type="FALSE_POSITIVE",
                    confidence=0.0,
                    matched_text=match.group(0),
                    snippet=snippet,
                )
            return MatchResult(
                matched=True,
                match_type="PROBABLE",
                confidence=0.75,
                matched_text=match.group(0),
                snippet=snippet,
            )
            
    # 4. Weak match: national digits without country code
    national_digits = phone.digits_only[len(str(phone.country_code)):] if len(phone.digits_only) > 10 else phone.digits_only
    if national_digits and len(national_digits) >= 10:
        pattern = re.compile(rf"(?<!\d){re.escape(national_digits)}(?!\d)")
        match = pattern.search(clean_text)
        if match:
            idx = match.start()
            snippet = extract_context_snippet(clean_text, idx, match.end())
            return MatchResult(
                matched=True,
                match_type="WEAK",
                confidence=0.45,
                matched_text=match.group(0),
                snippet=snippet,
            )
            
    return MatchResult(
        matched=False,
        match_type="NONE",
        confidence=0.0,
        matched_text="",
        snippet="",
    )
