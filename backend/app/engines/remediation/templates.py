"""Legal and Regulatory Privacy Notice Template Generator.
Generates formally grounded CCPA/CPRA, GDPR, TCPA, and telecom complaint notices
with customizable fields and masked identifiers.
"""

from dataclasses import dataclass
from typing import Optional
import datetime
from backend.app.engines.discovery.normalizer import NormalizedPhone


@dataclass
class GeneratedTemplate:
    template_type: str
    title: str
    recipient_type: str  # "data_broker", "regulator", "merchant"
    subject_line: str
    body_markdown: str


def generate_ccpa_opt_out(phone: NormalizedPhone, recipient_name: str = "Data Broker Privacy Team", target_url: Optional[str] = None) -> GeneratedTemplate:
    """Generates a CCPA/CPRA Request to Delete Personal Information and Opt-Out of Sale."""
    today = datetime.date.today().isoformat()
    url_mention = f"\nSpecific listing URL: {target_url}" if target_url else ""
    
    body = f"""Date: {today}
To: Privacy Officer / Data Protection Officer, {recipient_name}
Subject: Formal Consumer Request to Delete and Opt-Out of Sale/Sharing under CCPA/CPRA

Dear Privacy Team,

I am writing to exercise my statutory rights as a consumer under the California Consumer Privacy Act of 2018 (as amended by the California Privacy Rights Act of 2020, Cal. Civ. Code § 1798.100 et seq.).

Specifically, I hereby request that {recipient_name}:
1. PERMANENTLY DELETE all personal information that your business has collected or maintained about me, including but not limited to my telephone number ({phone.national} / {phone.e164}), associated names, historical addresses, and contact records.{url_mention}
2. OPT OUT of any future sale, disclosure, licensing, or sharing of my personal information to third parties (Cal. Civ. Code § 1798.120).
3. DIRECT all service providers, contractors, and third-party syndicates to delete my personal information from their respective records (Cal. Civ. Code § 1798.105(c)).

Identifying Telephone Information:
- Telephone Number: {phone.e164}
- Formatted National Variant: {phone.national}

Please confirm receipt of this request within 10 business days and confirm full completion within 45 calendar days as mandated by California law.

Sincerely,
Verified Telephone Subscriber
"""
    return GeneratedTemplate(
        template_type="CCPA_DELETE",
        title="CCPA / CPRA Request to Delete & Opt-Out of Sale",
        recipient_type="data_broker",
        subject_line=f"CCPA/CPRA Consumer Privacy Request — Telephone Suppression",
        body_markdown=body,
    )


def generate_gdpr_erasure(phone: NormalizedPhone, recipient_name: str = "Data Protection Officer", target_url: Optional[str] = None) -> GeneratedTemplate:
    """Generates a GDPR Article 17 (Right to Erasure) and Article 21 (Right to Object) Notice."""
    today = datetime.date.today().isoformat()
    url_mention = f"\nTarget Data Exposure URL: {target_url}" if target_url else ""

    body = f"""Date: {today}
To: Data Protection Officer, {recipient_name}
Subject: Notice of Exercise of Rights under GDPR (Article 17 Right to Erasure & Article 21 Right to Object)

Dear Data Protection Officer,

I am writing in my capacity as a data subject to formally exercise my statutory rights under the General Data Protection Regulation (Regulation (EU) 2016/679 and UK GDPR).

Pursuant to Article 17 of the GDPR ('Right to Erasure / Right to be Forgotten'), I formally request the immediate erasure of all personal data concerning me held by your organization, specifically:
- Telephone Number: {phone.e164} ({phone.international}){url_mention}

Pursuant to Article 21 of the GDPR, I hereby object to any further processing of my personal data for direct marketing, profiling, or public dissemination purposes.

Please note that under Article 12(3) of the GDPR, you are required to respond to this request without undue delay and at the latest within one calendar month of receipt.

If you fail to comply or provide an incomplete response, I reserve the right to lodge a formal complaint with the competent Supervisory Authority.

Sincerely,
Data Subject / Registered Telephone Subscriber
"""
    return GeneratedTemplate(
        template_type="GDPR_ERASURE",
        title="GDPR Article 17 Right to Erasure (Right to be Forgotten)",
        recipient_type="data_broker",
        subject_line=f"GDPR Article 17 Erasure Request — Telephone Data",
        body_markdown=body,
    )


def generate_tcpa_ftc_complaint(phone: NormalizedPhone, violator_number: str, incident_date: str, call_description: str) -> GeneratedTemplate:
    """Generates an FTC/FCC Do Not Call violation complaint record under the TCPA."""
    body = f"""FEDERAL TRADE COMMISSION & FCC TCPA VIOLATION RECORD
Registered Subscriber Number: {phone.national} ({phone.e164})
National Do Not Call Status: Registered on National DND Registry
Violator / Caller ID Displayed: {violator_number}
Date and Time of Unsolicited Contact: {incident_date}
Incident Description: {call_description}

Statutory Violations Identified:
1. Violation of the Telemarketing Sales Rule (16 C.F.R. Part 310) for placing unsolicited telemarketing calls to a number listed on the National Do Not Call Registry.
2. Violation of the Telephone Consumer Protection Act (47 U.S.C. § 227) for non-consensual automated telemarketing / prerecorded robocall transmissions.

Submission Portal: https://reportfraud.ftc.gov/ or https://consumercomplaints.fcc.gov/
"""
    return GeneratedTemplate(
        template_type="TCPA_COMPLAINT",
        title="US FTC / FCC Do Not Call Violation Complaint",
        recipient_type="regulator",
        subject_line=f"FTC / FCC Do Not Call Violation Report: {violator_number}",
        body_markdown=body,
    )


def generate_trai_1909_complaint(phone: NormalizedPhone, violator_number: str, incident_date_ddmmyy: str, incident_time: str) -> GeneratedTemplate:
    """Generates the official TRAI 1909 Unsolicited Commercial Communication (UCC) SMS format."""
    sms_text = f"COMP TEL NO {violator_number}, {incident_date_ddmmyy}, {incident_time}"
    body = f"""TRAI DND COMPLAINT PROCEDURE (INDIA)

Under TRAI Telecom Commercial Communications Customer Preference Regulations (TCCCPR 2018):
Send an SMS to shortcode: 1909
From your registered number: {phone.e164}

EXACT SMS TEXT TO SEND (Copy to clipboard):
--------------------------------------------------
{sms_text}
--------------------------------------------------

Example: If you received spam from 9876543210 on 24th October at 14:30:
COMP TEL NO 9876543210, 24/10/26, 14:30

Note: Must be submitted within 3 days of receiving the unsolicited communication.
Your telecom operator (Airtel/Jio/Vi) will issue a formal complaint ticket and investigate the offending telemarketer.
"""
    return GeneratedTemplate(
        template_type="TRAI_1909",
        title="India TRAI 1909 UCC Complaint Format",
        recipient_type="regulator",
        subject_line=f"TRAI 1909 Complaint — {violator_number}",
        body_markdown=body,
    )


def generate_merchant_unsubscribe(phone: NormalizedPhone, merchant_name: str) -> GeneratedTemplate:
    """Generates a formal Stop Processing / Unsubscribe demand for a commercial company."""
    today = datetime.date.today().isoformat()
    body = f"""Date: {today}
To: Customer Support / Marketing Operations, {merchant_name}
Subject: Request to Revoke Marketing Consent and Remove Telephone Number

Hello {merchant_name} Team,

I am writing to formally revoke any previously granted consent to contact me for marketing, promotional, or sales purposes.

Please immediately remove my telephone number from all marketing databases, SMS promotional lists, automated dialers, and affiliate contact sharing systems:
- Telephone Number: {phone.national} ({phone.e164})

Please confirm that this opt-out has been processed within 10 business days.

Thank you for your prompt cooperation.

Sincerely,
{phone.masked_display}
"""
    return GeneratedTemplate(
        template_type="MERCHANT_UNSUBSCRIBE",
        title="Universal Merchant Direct Unsubscribe Notice",
        recipient_type="merchant",
        subject_line=f"Revocation of Contact Consent — {phone.masked_display}",
        body_markdown=body,
    )


def generate_dpdp_act_notice(
    phone: NormalizedPhone,
    business_name: str,
    grievance_email: Optional[str] = None,
    target_url: Optional[str] = None,
) -> GeneratedTemplate:
    """Generates a formal legal notice under Section 6(4) and Section 12 of India's Digital Personal Data Protection Act, 2023."""
    today = datetime.date.today().isoformat()
    recipient_email = grievance_email or "grievance-officer@" + business_name.lower().replace(" ", "") + ".in"
    url_mention = f"\nSpecific Data Exposure URL: {target_url}" if target_url else ""

    body = f"""FORMAL NOTICE: REVOCATION OF MARKETING CONSENT & DATA ERASURE REQUEST
Under Section 6(4) and Section 12 of the Digital Personal Data Protection Act (DPDP Act), 2023
and Rule 5(7) of the Information Technology (Intermediary Guidelines) Rules.

Date: {today}
To:
Grievance Officer / Data Protection Officer, {business_name}
Email: {recipient_email}

Subject: Immediate Revocation of Marketing Consent and Permanent Suppression of Telephone Number {phone.masked_display}

Dear Grievance Officer,

I am writing to formally exercise my statutory rights as a Data Principal under Section 6(4) and Section 12 of the Digital Personal Data Protection Act (DPDP Act), 2023.

1. Revocation of Consent (Section 6(4)):
I hereby withdraw and revoke all previously granted consent (express, implied, or transactional) permitting {business_name}, its marketing affiliates, and contracted telemarketing agencies to process my personal data for promotional SMS, telemarketing calls, or cross-sell campaigns.

2. Permanent Telephone Number Suppression:
Please immediately suppress my telephone number from all active outbound campaigns, telemarketing dialers, and promotional databases:
- Telephone Number (E.164): {phone.e164}
- Formatted Domestic Variant: {phone.national}
- Masked Identifier: {phone.masked_display}{url_mention}

3. Erasure of Non-Essential Personal Data (Section 12):
In accordance with Section 12 of the DPDP Act 2023, please erase and purge all marketing profiles, lead scoring attributes, and contact records associated with my telephone number.

4. Statutory Compliance Confirmation:
Please confirm compliance with this revocation notice in writing to this email within the statutory timeframe mandated by Indian law. If unsolicited commercial communications continue from your registered DLT headers, this matter will be formally escalated to the Data Protection Board of India and the Telecom Regulatory Authority of India (TRAI).

Yours faithfully,
Verified Data Principal
Contact Reference: {phone.masked_display}
"""
    return GeneratedTemplate(
        template_type="DPDP_ACT_2023",
        title="India DPDP Act 2023 Consent Revocation & Data Erasure Notice",
        recipient_type="data_fiduciary",
        subject_line=f"DPDP Act 2023 Notice — Revocation of Consent for {phone.masked_display}",
        body_markdown=body,
    )

