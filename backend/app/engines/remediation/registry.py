"""Source Remediation Registry.
Maintains a curated catalog of 25+ verified opt-out mechanisms, official removal URLs,
submission requirements, turnaround time estimates, and statutory rights across
major data brokers, people directories, search engines, and regulatory bodies.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from urllib.parse import urlparse


@dataclass
class RemediationSource:
    source_id: str
    name: str
    category: str  # "data_broker", "people_directory", "search_engine", "public_paste", "telecom"
    domains: List[str]
    official_removal_url: str
    removal_method: str  # "online_form", "email_request", "assisted_mail", "telecom_dnd", "search_deindex"
    instructions: List[str]
    processing_time_estimate: str
    requires_email_confirmation: bool
    requires_phone_call: bool
    statutory_rights: List[str]  # e.g. ["CCPA", "GDPR", "TRAI", "DPDP Act 2023"]
    contact_email: Optional[str] = None
    notes: Optional[str] = None
    execution_type: Optional[str] = None
    verification_status: Optional[str] = None
    lookup_method: Optional[str] = None
    can_match_phone: Optional[bool] = None
    evidence_attribution: Optional[str] = None
    last_verified_at: Optional[str] = None


REMEDIATION_REGISTRY: Dict[str, RemediationSource] = {
    # --- US Major People Search Directories & Data Brokers ---
    "fastpeoplesearch": RemediationSource(
        source_id="fastpeoplesearch",
        name="FastPeopleSearch",
        category="people_directory",
        domains=["fastpeoplesearch.com"],
        official_removal_url="https://www.fastpeoplesearch.com/removal",
        removal_method="online_form",
        instructions=[
            "1. Visit https://www.fastpeoplesearch.com/removal in your browser.",
            "2. Enter an email address to receive the verification link and accept terms.",
            "3. Search for your profile using your phone number or full name.",
            "4. Open your matching record and click 'Remove My Record'.",
            "5. Open your email inbox and click the confirmation link sent by FastPeopleSearch within 24 hours.",
        ],
        processing_time_estimate="24 to 72 hours",
        requires_email_confirmation=True,
        requires_phone_call=False,
        statutory_rights=["CCPA", "General Privacy"],
        contact_email="privacy@fastpeoplesearch.com",
        notes="Removal suppresses current profile; re-check after 6 months as public records update.",
    ),

    "truepeoplesearch": RemediationSource(
        source_id="truepeoplesearch",
        name="TruePeopleSearch",
        category="people_directory",
        domains=["truepeoplesearch.com"],
        official_removal_url="https://www.truepeoplesearch.com/removal",
        removal_method="online_form",
        instructions=[
            "1. Visit https://www.truepeoplesearch.com/removal.",
            "2. Select 'The subject of the request' and provide your email address.",
            "3. Check your email inbox for the verification message and click the validation link.",
            "4. Search for your record on the redirected page.",
            "5. Click 'Remove This Record' on your profile detail view.",
        ],
        processing_time_estimate="24 to 48 hours",
        requires_email_confirmation=True,
        requires_phone_call=False,
        statutory_rights=["CCPA", "General Privacy"],
        contact_email="support@truepeoplesearch.com",
        notes="Fastest online broker opt-out in the US.",
    ),

    "whitepages": RemediationSource(
        source_id="whitepages",
        name="Whitepages",
        category="people_directory",
        domains=["whitepages.com"],
        official_removal_url="https://www.whitepages.com/suppression-requests",
        removal_method="online_form",
        instructions=[
            "1. Go to whitepages.com and search for your listing by phone number or name.",
            "2. Copy the complete profile URL from your browser's address bar.",
            "3. Navigate to https://www.whitepages.com/suppression-requests.",
            "4. Paste your profile URL and confirm the record.",
            "5. Provide a contact phone number to receive an automated verification code (enter the 4-digit code on screen).",
        ],
        processing_time_estimate="24 to 48 hours",
        requires_email_confirmation=False,
        requires_phone_call=True,
        statutory_rights=["CCPA", "General Privacy"],
        contact_email="support@whitepages.com",
        notes="Requires automated phone call verification code.",
    ),

    "radaris": RemediationSource(
        source_id="radaris",
        name="Radaris",
        category="data_broker",
        domains=["radaris.com"],
        official_removal_url="https://radaris.com/control/privacy",
        removal_method="online_form",
        instructions=[
            "1. Open https://radaris.com/control/privacy.",
            "2. Search for your profile name or phone number.",
            "3. Select the matching listing and click 'Control Info' / 'Remove Info'.",
            "4. Enter your email address to receive the confirmation link.",
            "5. Click the verification link in your inbox.",
        ],
        processing_time_estimate="48 hours",
        requires_email_confirmation=True,
        requires_phone_call=False,
        statutory_rights=["CCPA", "General Privacy"],
        contact_email="customer-service@radaris.com",
        notes="Suppression removes public exposure but retains a cryptographic tombstone.",
    ),

    "spokeo": RemediationSource(
        source_id="spokeo",
        name="Spokeo",
        category="data_broker",
        domains=["spokeo.com"],
        official_removal_url="https://www.spokeo.com/optout",
        removal_method="online_form",
        instructions=[
            "1. Search spokeo.com for your phone number to locate your listing URL.",
            "2. Copy the profile URL from your browser address bar.",
            "3. Go to https://www.spokeo.com/optout.",
            "4. Paste the profile URL and enter a contact email address.",
            "5. Click the confirmation link in the email sent by Spokeo.",
        ],
        processing_time_estimate="24 to 72 hours",
        requires_email_confirmation=True,
        requires_phone_call=False,
        statutory_rights=["CCPA", "General Privacy"],
        contact_email="privacy@spokeo.com",
        notes="Confirmation email expires after 24 hours.",
    ),

    "nuwber": RemediationSource(
        source_id="nuwber",
        name="Nuwber",
        category="people_directory",
        domains=["nuwber.com"],
        official_removal_url="https://nuwber.com/removal/link",
        removal_method="online_form",
        instructions=[
            "1. Search nuwber.com for your phone number or name.",
            "2. Copy the specific profile URL.",
            "3. Navigate to https://nuwber.com/removal/link.",
            "4. Paste the URL and your email address.",
            "5. Click the verification link in the confirmation email.",
        ],
        processing_time_estimate="24 to 48 hours",
        requires_email_confirmation=True,
        requires_phone_call=False,
        statutory_rights=["CCPA", "General Privacy"],
        contact_email="support@nuwber.com",
        notes="Nuwber processes removals within 48 hours.",
    ),

    "cyberbackgroundchecks": RemediationSource(
        source_id="cyberbackgroundchecks",
        name="CyberBackgroundChecks",
        category="people_directory",
        domains=["cyberbackgroundchecks.com"],
        official_removal_url="https://www.cyberbackgroundchecks.com/removal",
        removal_method="online_form",
        instructions=[
            "1. Visit https://www.cyberbackgroundchecks.com/removal.",
            "2. Accept terms, enter your email address, and complete verification.",
            "3. Search for your record and click 'Remove My Record'.",
            "4. Verify via email link.",
        ],
        processing_time_estimate="24 to 72 hours",
        requires_email_confirmation=True,
        requires_phone_call=False,
        statutory_rights=["CCPA", "General Privacy"],
        contact_email="support@cyberbackgroundchecks.com",
        notes="Strict bot detection on form; complete in standard desktop browser.",
    ),

    "thatsthem": RemediationSource(
        source_id="thatsthem",
        name="That's Them",
        category="people_directory",
        domains=["thatsthem.com"],
        official_removal_url="https://thatsthem.com/opt-out",
        removal_method="online_form",
        instructions=[
            "1. Go to https://thatsthem.com/opt-out.",
            "2. Enter your full name, phone number, and street address.",
            "3. Submit the form to suppress matching records.",
        ],
        processing_time_estimate="24 hours",
        requires_email_confirmation=False,
        requires_phone_call=False,
        statutory_rights=["CCPA", "General Privacy"],
        contact_email="support@thatsthem.com",
        notes="Instant automated suppression once submitted.",
    ),

    "beenverified": RemediationSource(
        source_id="beenverified",
        name="BeenVerified",
        category="data_broker",
        domains=["beenverified.com"],
        official_removal_url="https://www.beenverified.com/app/optout/search",
        removal_method="online_form",
        instructions=[
            "1. Go to https://www.beenverified.com/app/optout/search.",
            "2. Search by name and state.",
            "3. Click 'Opt Out' on your profile and provide your email.",
            "4. Click the confirmation link sent to your email inbox.",
        ],
        processing_time_estimate="3 to 5 business days",
        requires_email_confirmation=True,
        requires_phone_call=False,
        statutory_rights=["CCPA", "General Privacy"],
        contact_email="privacy@beenverified.com",
        notes="Parent company also operates NeighborWho and Ownerly.",
    ),

    "intelius": RemediationSource(
        source_id="intelius",
        name="Intelius",
        category="data_broker",
        domains=["intelius.com"],
        official_removal_url="https://www.intelius.com/opt-out/submit/",
        removal_method="online_form",
        instructions=[
            "1. Open https://www.intelius.com/opt-out/submit/.",
            "2. Search for your record and select it.",
            "3. Submit email address and confirm link.",
        ],
        processing_time_estimate="3 to 7 days",
        requires_email_confirmation=True,
        requires_phone_call=False,
        statutory_rights=["CCPA", "General Privacy"],
        contact_email="privacy@intelius.com",
        notes="Operated by PeopleConnect; covers USSearch and Classmates.",
    ),

    # --- Search Engines & De-indexing ---
    "google_search": RemediationSource(
        source_id="google_search",
        name="Google Search (PII & Outdated Removal)",
        category="search_engine",
        domains=["google.com", "google.co.uk", "google.ca"],
        official_removal_url="https://support.google.com/websearch/troubleshooter/3111061",
        removal_method="search_deindex",
        instructions=[
            "1. If the underlying website has removed your number, use the Outdated Content Tool: https://search.google.com/search-console/remove-outdated-content.",
            "2. If the page is still live and exposes personal contact info, use the Personal Information Removal Request: https://support.google.com/websearch/troubleshooter/3111061.",
            "3. Provide the search result URL, the page URL, and the exact phone number snippet displayed.",
            "4. Google reviews requests within 2 to 5 business days and de-indexes the URL from search results.",
        ],
        processing_time_estimate="2 to 5 business days",
        requires_email_confirmation=True,
        requires_phone_call=False,
        statutory_rights=["Google Policy", "GDPR (Right to be Forgotten)"],
        contact_email=None,
        notes="De-indexes search snippet even if third-party webmaster is unresponsive.",
    ),

    "bing_search": RemediationSource(
        source_id="bing_search",
        name="Bing Search Content Removal",
        category="search_engine",
        domains=["bing.com"],
        official_removal_url="https://www.bing.com/webmasters/tools/contentremoval",
        removal_method="search_deindex",
        instructions=[
            "1. Visit https://www.bing.com/webmasters/tools/contentremoval.",
            "2. Sign in with a free Microsoft account.",
            "3. Enter the URL of the cached result and the outdated phone number.",
            "4. Submit removal request for review.",
        ],
        processing_time_estimate="3 to 7 business days",
        requires_email_confirmation=False,
        requires_phone_call=False,
        statutory_rights=["Bing Policy", "GDPR"],
        contact_email=None,
        notes="Removes cached preview snippets from Bing search results.",
    ),

    # --- Code & Pastes ---
    "github": RemediationSource(
        source_id="github",
        name="GitHub Public Repositories",
        category="public_paste",
        domains=["github.com", "raw.githubusercontent.com", "gist.github.com"],
        official_removal_url="https://docs.github.com/en/site-policy/content-removal-policies/github-private-information-removal-policy",
        removal_method="online_form",
        instructions=[
            "1. First, attempt to contact the repository owner or open an issue requesting removal.",
            "2. If uncooperative or unaddressed, file a Private Information Removal Request at https://support.github.com/contact/private-information.",
            "3. Include links to the exact commit, file path, and lines containing your phone number.",
        ],
        processing_time_estimate="24 to 48 hours",
        requires_email_confirmation=True,
        requires_phone_call=False,
        statutory_rights=["GitHub Terms", "DMCA/Privacy"],
        contact_email="support@github.com",
        notes="GitHub can purge commits containing unredacted personal telephone numbers.",
    ),

    "pastebin": RemediationSource(
        source_id="pastebin",
        name="Pastebin",
        category="public_paste",
        domains=["pastebin.com"],
        official_removal_url="https://pastebin.com/report",
        removal_method="online_form",
        instructions=[
            "1. Open the specific paste URL on pastebin.com.",
            "2. Click the 'Report' button or navigate to https://pastebin.com/report.",
            "3. Select 'Personal Information' as reason and include the paste URL.",
            "4. Pastebin staff typically removes offending pastes within 12 hours.",
        ],
        processing_time_estimate="12 to 24 hours",
        requires_email_confirmation=False,
        requires_phone_call=False,
        statutory_rights=["Pastebin Terms"],
        contact_email="abuse@pastebin.com",
        notes="Pastes containing doxxing or personal numbers are removed quickly.",
    ),

    # --- National Telecom DND & Regulatory Channels ---
    "us_ftc_dnd": RemediationSource(
        source_id="us_ftc_dnd",
        name="US National Do Not Call Registry (FTC)",
        category="telecom",
        domains=["donotcall.gov", "ftc.gov"],
        official_removal_url="https://www.donotcall.gov/register.html",
        removal_method="telecom_dnd",
        instructions=[
            "1. Visit https://www.donotcall.gov/register.html.",
            "2. Register up to 3 personal telephone numbers and provide your email.",
            "3. Click the verification link sent to your email within 72 hours.",
            "4. Telemarketers have a statutory obligation under federal law to scrub registered numbers within 31 days.",
            "5. If illegal calls persist after 31 days, file a formal complaint at https://reportfraud.ftc.gov/.",
        ],
        processing_time_estimate="31 days statutory window",
        requires_email_confirmation=True,
        requires_phone_call=False,
        statutory_rights=["Telephone Consumer Protection Act (TCPA)", "FTC Telemarketing Sales Rule"],
        contact_email=None,
        notes="Registration is permanent and free under US federal law.",
    ),

    "uk_tps": RemediationSource(
        source_id="uk_tps",
        name="UK Telephone Preference Service (TPS)",
        category="telecom",
        domains=["tpsonline.org.uk"],
        official_removal_url="https://www.tpsonline.org.uk/register",
        removal_method="telecom_dnd",
        instructions=[
            "1. Visit https://www.tpsonline.org.uk/register or text 'TPS' and your email to 85095 from your UK mobile.",
            "2. Complete email confirmation.",
            "3. Telemarketers are legally barred under PECR regulations from calling after 28 days.",
            "4. Report persistent nuisance calls to the Information Commissioner's Office (ICO).",
        ],
        processing_time_estimate="28 days statutory window",
        requires_email_confirmation=True,
        requires_phone_call=False,
        statutory_rights=["PECR (UK)", "UK GDPR"],
        contact_email="tps@dma.org.uk",
        notes="Free statutory opt-out for UK mobile and landline numbers.",
    ),

    "india_trai_1909": RemediationSource(
        source_id="india_trai_1909",
        name="India National Customer Preference Register (TRAI 1909)",
        category="telecom",
        domains=["trai.gov.in"],
        official_removal_url="https://www.trai.gov.in/consumer-info/telecom/dnd",
        removal_method="telecom_dnd",
        instructions=[
            "1. Send an SMS 'START 0' to 1909 to block all commercial telemarketing categories.",
            "2. Alternatively, dial 1909 (toll-free IVR) from your registered mobile number.",
            "3. To report an unsolicited commercial call/SMS, send SMS to 1909 within 3 days in format:",
            "   'COMP TEL NO XXXXXXXXXX, dd/mm/yy, Time' (e.g. COMP TEL NO 9876543210, 24/10/26, 14:30)",
            "4. Carrier investigates and disconnects repeat telemarketing offenders under TRAI TCCCPR regulations.",
        ],
        processing_time_estimate="7 days statutory window",
        requires_email_confirmation=False,
        requires_phone_call=False,
        statutory_rights=["TRAI TCCCPR Regulations 2018"],
        contact_email="dnd@trai.gov.in",
        notes="Official TRAI 1909 shortcode supported by Airtel, Jio, and Vi.",
    ),

    "canada_dncl": RemediationSource(
        source_id="canada_dncl",
        name="Canada National Do Not Call List (CRTC)",
        category="telecom",
        domains=["lnnte-dncl.gc.ca", "crtc.gc.ca"],
        official_removal_url="https://lnnte-dncl.gc.ca/en/Consumer/Register-your-number",
        removal_method="telecom_dnd",
        instructions=[
            "1. Visit https://lnnte-dncl.gc.ca/en/Consumer/Register-your-number.",
            "2. Enter your 10-digit Canadian phone number.",
            "3. Registration takes effect within 31 days.",
            "4. File violations with the CRTC via the online complaint portal.",
        ],
        processing_time_estimate="31 days statutory window",
        requires_email_confirmation=False,
        requires_phone_call=False,
        statutory_rights=["Telecommunications Act (Canada)"],
        contact_email=None,
        notes="Registration is permanent and does not expire.",
    ),

    "australia_dncr": RemediationSource(
        source_id="australia_dncr",
        name="Australia Do Not Call Register (ACMA)",
        category="telecom",
        domains=["donotcall.gov.au", "acma.gov.au"],
        official_removal_url="https://www.donotcall.gov.au/consumers/register-your-numbers/",
        removal_method="telecom_dnd",
        instructions=[
            "1. Visit https://www.donotcall.gov.au/consumers/register-your-numbers/.",
            "2. Enter your Australian phone number and email address.",
            "3. Confirm via the email verification link.",
            "4. Takes effect within 30 days under ACMA regulations.",
        ],
        processing_time_estimate="30 days statutory window",
        requires_email_confirmation=True,
        requires_phone_call=False,
        statutory_rights=["Do Not Call Register Act 2006 (Australia)"],
        contact_email=None,
        notes="Permanent registration managed by the ACMA.",
    ),
}

# --- Integrate 110+ Curated Indian Sources ---
from backend.app.engines.remediation.india_registry import INDIAN_SOURCE_INVENTORY

for _tid, _target in INDIAN_SOURCE_INVENTORY.items():
    REMEDIATION_REGISTRY[_tid] = RemediationSource(
        source_id=_target.source_id,
        name=_target.name,
        category=_target.category_label,
        domains=_target.domains,
        official_removal_url=_target.official_url,
        removal_method=_target.execution_type,
        instructions=_target.instructions,
        processing_time_estimate="Immediate" if _target.execution_type == "manual_browser" else "24 to 72 hours",
        requires_email_confirmation=False,
        requires_phone_call=False,
        statutory_rights=_target.statutory_rights,
        contact_email=_target.grievance_email,
        notes=f"{_target.category_label} | {_target.known_limitations}",
        execution_type=_target.execution_type,
        verification_status=_target.verification_status,
        lookup_method=_target.lookup_method,
        can_match_phone=_target.can_match_phone,
        evidence_attribution=_target.evidence_attribution,
        last_verified_at=_target.last_verified_at,
    )



def lookup_source_by_url(url: str) -> Optional[RemediationSource]:
    """Finds a matching remediation source by URL hostname or domain."""
    if not url:
        return None
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        
        for source in REMEDIATION_REGISTRY.values():
            for d in source.domains:
                if netloc == d or netloc.endswith("." + d):
                    return source
    except Exception:
        pass
    return None


def get_all_sources() -> List[RemediationSource]:
    """Returns all registered remediation sources sorted by category and name."""
    return sorted(REMEDIATION_REGISTRY.values(), key=lambda s: (s.category, s.name))
