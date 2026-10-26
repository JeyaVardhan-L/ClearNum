"""Country-specific Telecom Do Not Call (DND) and Spam Complaint Guides.
Covers statutory opt-out registries, carrier 7726 forwarding, and regulatory channels.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class DNDCountryGuide:
    country_code: str
    country_name: str
    registry_name: str
    official_website: str
    statutory_window: str
    how_to_register: List[str]
    carrier_spam_forwarding_code: Optional[str]
    carrier_forwarding_instructions: str
    how_to_file_complaint: List[str]
    legal_basis: str


COUNTRY_DND_GUIDES: Dict[str, DNDCountryGuide] = {
    "US": DNDCountryGuide(
        country_code="US",
        country_name="United States",
        registry_name="National Do Not Call Registry",
        official_website="https://www.donotcall.gov/",
        statutory_window="31 calendar days",
        how_to_register=[
            "Visit https://www.donotcall.gov/register.html or call 1-888-382-1222 from the phone you wish to register.",
            "Enter your phone number and email address.",
            "Click the confirmation link sent to your email within 72 hours.",
            "Registration is completely free and never expires under federal law.",
        ],
        carrier_spam_forwarding_code="7726 (SPAM)",
        carrier_forwarding_instructions="Forward any unsolicited spam SMS message to shortcode 7726 (spells SPAM). Supported by AT&T, Verizon, T-Mobile. Your carrier will request the sender number and add it to global network-level spam filters.",
        how_to_file_complaint=[
            "Wait 31 days after registering on DoNotCall.gov.",
            "If an illegal telemarketing call or robocall occurs, note the date, time, and caller ID displayed.",
            "File a complaint at https://reportfraud.ftc.gov/ or https://consumercomplaints.fcc.gov/.",
            "Complaints are forwarded to state attorneys general and federal law enforcement.",
        ],
        legal_basis="Telephone Consumer Protection Act of 1991 (TCPA, 47 U.S.C. § 227) & FTC Telemarketing Sales Rule (16 C.F.R. Part 310).",
    ),

    "GB": DNDCountryGuide(
        country_code="GB",
        country_name="United Kingdom",
        registry_name="Telephone Preference Service (TPS)",
        official_website="https://www.tpsonline.org.uk/",
        statutory_window="28 calendar days",
        how_to_register=[
            "Visit https://www.tpsonline.org.uk/register.",
            "Alternatively, send an SMS with the word 'TPS' followed by your email address to 85095 (free from UK mobiles).",
            "Follow the email confirmation prompt.",
        ],
        carrier_spam_forwarding_code="7726",
        carrier_forwarding_instructions="Forward suspicious marketing SMS messages to 7726. Supported by EE, Vodafone, O2, and Three.",
        how_to_file_complaint=[
            "Wait 28 days following your TPS registration.",
            "Report unwanted sales calls or spam texts directly to the Information Commissioner's Office (ICO): https://ico.org.uk/make-a-complaint/nuisance-calls-and-messages/.",
        ],
        legal_basis="Privacy and Electronic Communications Regulations (PECR) 2003 and UK GDPR.",
    ),

    "IN": DNDCountryGuide(
        country_code="IN",
        country_name="India",
        registry_name="National Customer Preference Register (NCPR / 1909)",
        official_website="https://www.trai.gov.in/consumer-info/telecom/dnd",
        statutory_window="7 calendar days",
        how_to_register=[
            "Send an SMS 'START 0' to toll-free shortcode 1909 to register for full commercial communication blocking.",
            "Alternatively, dial 1909 (toll-free IVR) from your registered mobile number and follow the voice prompts.",
            "Download and use the official TRAI DND 3.0 app for Android/iOS.",
        ],
        carrier_spam_forwarding_code="1909",
        carrier_forwarding_instructions="To register a commercial communication complaint, send SMS to 1909 in format: 'COMP TEL NO XXXXXXXXXX, dd/mm/yy, Time' within 3 days of receipt.",
        how_to_file_complaint=[
            "Send complaint SMS to 1909 within 3 days of receiving spam call/SMS.",
            "Your access provider (Airtel, Jio, Vi, BSNL) will issue a complaint registration number.",
            "The telecom provider is statutorily required to complete an investigation and notify you within 7 days.",
            "Repeat telemarketing violators face financial penalties and disconnection.",
        ],
        legal_basis="Telecom Commercial Communications Customer Preference Regulations, 2018 (TCCCPR 2018) enforced by TRAI.",
    ),

    "CA": DNDCountryGuide(
        country_code="CA",
        country_name="Canada",
        registry_name="National Do Not Call List (DNCL)",
        official_website="https://lnnte-dncl.gc.ca/en",
        statutory_window="31 calendar days",
        how_to_register=[
            "Visit https://lnnte-dncl.gc.ca/en/Consumer/Register-your-number.",
            "Call 1-866-580-DNCL (1-866-580-3625) from the phone number to register.",
            "Registration is permanent and does not need to be renewed.",
        ],
        carrier_spam_forwarding_code="7726 (SPAM)",
        carrier_forwarding_instructions="Forward unsolicited spam SMS to 7726 (Bell, Rogers, Telus).",
        how_to_file_complaint=[
            "Submit a violation report to the Canadian Radio-television and Telecommunications Commission (CRTC) at https://lnnte-dncl.gc.ca/en/Consumer/File-a-complaint/.",
            "For email/SMS spam, report to the Spam Reporting Centre at https://fightspam.gc.ca/.",
        ],
        legal_basis="Telecommunications Act and Canada's Anti-Spam Legislation (CASL).",
    ),

    "AU": DNDCountryGuide(
        country_code="AU",
        country_name="Australia",
        registry_name="Do Not Call Register (ACMA)",
        official_website="https://www.donotcall.gov.au/",
        statutory_window="30 calendar days",
        how_to_register=[
            "Visit https://www.donotcall.gov.au/consumers/register-your-numbers/.",
            "Enter your phone number and confirm via email.",
            "Alternatively, call 1300 792 958 from the number.",
        ],
        carrier_spam_forwarding_code="0429 999 888 / 7726",
        carrier_forwarding_instructions="Forward SMS spam to ACMA's dedicated mobile number 0429 999 888 or carrier shortcode 7726 (Telstra, Optus).",
        how_to_file_complaint=[
            "After 30 days of registration, report telemarketing breaches directly to the Australian Communications and Media Authority (ACMA): https://www.donotcall.gov.au/consumers/lodge-a-complaint/.",
        ],
        legal_basis="Do Not Call Register Act 2006 and Spam Act 2003 (Australia).",
    ),
}


def get_dnd_guide_for_country(country_code: str) -> Optional[DNDCountryGuide]:
    """Returns the DND guide for a given ISO 2-letter country code (e.g. US, GB, IN, CA, AU)."""
    return COUNTRY_DND_GUIDES.get(country_code.upper())


def get_all_dnd_guides() -> List[DNDCountryGuide]:
    """Returns all available national telecom DND guides."""
    return list(COUNTRY_DND_GUIDES.values())
