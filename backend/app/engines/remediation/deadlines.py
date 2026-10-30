"""Transparent Statutory and Estimated Remediation Deadline Calculator.
Calculates actionable response windows based on jurisdiction, template type, and statutory rules.
Never infers a statutory basis merely from template type string without verifying jurisdiction.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional


@dataclass
class DeadlineInfo:
    days: int
    expected_response_date: str  # YYYY-MM-DD
    follow_up_date: str          # YYYY-MM-DD
    deadline_basis: str          # "STATUTORY", "SOURCE_ESTIMATE", "USER_DEFINED", "NONE"
    citation: str
    is_estimate: bool
    notes: str


def calculate_remediation_deadline(
    request_type: str,
    jurisdiction: Optional[str] = "IN",
    start_date: Optional[str] = None,
    custom_days: Optional[int] = None,
    user_basis: Optional[str] = None,
) -> DeadlineInfo:
    """Calculates response and follow-up deadlines for remediation requests.
    Enforces truthful statutory grounding: non-matching jurisdictions are categorized
    as SOURCE_ESTIMATE or USER_DEFINED, never falsely labeled as STATUTORY.
    """
    req_upper = (request_type or "").upper().strip()
    jur_upper = (jurisdiction or "IN").upper().strip()

    # Parse start date or default to current UTC date
    if start_date:
        try:
            # Handle full ISO or YYYY-MM-DD
            clean_date = start_date.replace("Z", "+00:00")
            dt_start = datetime.fromisoformat(clean_date).date()
        except Exception:
            dt_start = datetime.now(timezone.utc).date()
    else:
        dt_start = datetime.now(timezone.utc).date()

    # If caller explicitly provided user_basis == "USER_DEFINED" with custom_days
    if user_basis == "USER_DEFINED" and custom_days is not None:
        days = max(1, custom_days)
        exp_date = (dt_start + timedelta(days=days)).isoformat()
        follow_date = (dt_start + timedelta(days=max(1, days // 2))).isoformat()
        return DeadlineInfo(
            days=days,
            expected_response_date=exp_date,
            follow_up_date=follow_date,
            deadline_basis="USER_DEFINED",
            citation="User-specified deadline timeline",
            is_estimate=False,
            notes="Manually entered deadline interval.",
        )

    # 1. CCPA / CPRA Deletion & Do-Not-Sell
    if req_upper in ("CCPA_DELETE", "CCPA_DELETION", "CCPA"):
        if jur_upper in ("US", "USA", "CA"):
            days = 45
            citation = "California Consumer Privacy Act (CCPA), Cal. Civ. Code § 1798.130"
            basis = "STATUTORY"
            is_estimate = False
            notes = "Business must confirm deletion within 45 calendar days of receipt."
        else:
            days = 45
            citation = "CCPA benchmark timeline (out-of-jurisdiction estimate)"
            basis = "SOURCE_ESTIMATE"
            is_estimate = True
            notes = f"Target jurisdiction is '{jur_upper}'; CCPA 45-day window applied as non-binding estimate only."

    # 2. GDPR Erasure & Right to Object
    elif req_upper in ("GDPR_ERASURE", "GDPR_DELETE", "GDPR"):
        if jur_upper in ("EU", "GB", "UK", "EEA", "DE", "FR", "NL", "IE", "ES", "IT"):
            days = 30
            citation = "General Data Protection Regulation (GDPR), Article 12(3)"
            basis = "STATUTORY"
            is_estimate = False
            notes = "Controller must respond without undue delay and at the latest within one month (30 days)."
        else:
            days = 30
            citation = "GDPR benchmark timeline (out-of-jurisdiction estimate)"
            basis = "SOURCE_ESTIMATE"
            is_estimate = True
            notes = f"Target jurisdiction is '{jur_upper}'; GDPR 30-day window applied as non-binding estimate only."

    # 3. TRAI TCCCPR Commercial Communication Violation
    elif req_upper in ("TRAI_1909", "TRAI_COMMERCIAL", "TRAI"):
        if jur_upper in ("IN", "IND", "INDIA"):
            days = 7
            citation = "Telecom Commercial Communications Customer Preference Regulations (TCCCPR), 2018"
            basis = "STATUTORY"
            is_estimate = False
            notes = "Access providers must take corrective action within 7 business days of grievance registration."
        else:
            days = 7
            citation = "TRAI 1909 guideline (India-only telecom regulation)"
            basis = "SOURCE_ESTIMATE"
            is_estimate = True
            notes = f"Target jurisdiction '{jur_upper}' is outside India; 7-day telecom timeline is an estimate."

    # 4. DPDP Act 2023 Consent Revocation & Erasure
    elif req_upper in ("DPDP_ACT_2023", "DPDP_NOTICE", "DPDP"):
        days = 30
        citation = "Digital Personal Data Protection Act (DPDP), 2023, Section 12 Grievance Redressal"
        if jur_upper in ("IN", "IND", "INDIA"):
            basis = "STATUTORY"
            is_estimate = False
            notes = "Standard statutory grievance redressal timeline of 30 days under Indian consumer framework; awaiting notified central rules."
        else:
            basis = "SOURCE_ESTIMATE"
            is_estimate = True
            notes = f"Target jurisdiction '{jur_upper}' is outside India; 30-day DPDP window applied as non-binding estimate."

    # 5. TCPA Revocation & Internal DNC
    elif req_upper in ("TCPA_COMPLAINT", "TCPA_REVOCATION", "TCPA"):
        if jur_upper in ("US", "USA"):
            days = 30
            citation = "Telephone Consumer Protection Act (TCPA), 47 CFR § 64.1200"
            basis = "STATUTORY"
            is_estimate = False
            notes = "Internal Do-Not-Call demand must be honored immediately, with carrier updates within 30 days."
        else:
            days = 30
            citation = "TCPA guideline (US-only telecom statute)"
            basis = "SOURCE_ESTIMATE"
            is_estimate = True
            notes = f"Target jurisdiction '{jur_upper}' is outside US; 30-day timeline is an estimate."

    # 6. Generic Web Form / Merchant Unsubscribe / Default
    elif req_upper in ("MERCHANT_UNSUBSCRIBE", "MERCHANT_OPTOUT"):
        days = 10
        citation = "CAN-SPAM Act / Commercial Email Best Practices"
        basis = "STATUTORY" if jur_upper in ("US", "USA") else "SOURCE_ESTIMATE"
        is_estimate = jur_upper not in ("US", "USA")
        notes = "Commercial opt-out requests typically honored within 10 business days."

    elif req_upper in ("WEB_FORM", "DIRECT_EMAIL", "SEARCH_DELIST"):
        days = 21
        citation = "Curated Broker Removal Industry Estimate"
        basis = "SOURCE_ESTIMATE"
        is_estimate = True
        notes = "Estimated median processing time across public broker opt-out queues (2–3 weeks)."

    else:
        days = 30
        citation = "Standard Privacy Request Window"
        basis = "SOURCE_ESTIMATE"
        is_estimate = True
        notes = "Standard 30-day response window for unstructured privacy requests."

    # If caller requested a custom day override but didn't specify user_basis
    if custom_days is not None and custom_days > 0:
        days = custom_days
        basis = "USER_DEFINED"
        is_estimate = False

    exp_date = (dt_start + timedelta(days=days)).isoformat()
    # Schedule follow-up roughly half-way or 7 days prior
    follow_offset = max(1, days - 7) if days > 14 else max(1, days // 2)
    follow_date = (dt_start + timedelta(days=follow_offset)).isoformat()

    return DeadlineInfo(
        days=days,
        expected_response_date=exp_date,
        follow_up_date=follow_date,
        deadline_basis=basis,
        citation=citation,
        is_estimate=is_estimate,
        notes=notes,
    )

