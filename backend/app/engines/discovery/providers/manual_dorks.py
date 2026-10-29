"""Manual Dorking Generator.
Produces pre-computed, URL-encoded search links across Google, Bing, Brave, Yahoo,
GitHub, Pastebin, and specialized Indian directories (Justdial, IndiaMART, Zauba Corp,
ConsumerComplaints, Indian Kanoon, MCA, etc.) for 1-click execution.
"""

from dataclasses import dataclass
from typing import List
from urllib.parse import quote_plus
from backend.app.engines.discovery.normalizer import NormalizedPhone


@dataclass
class ManualDork:
    engine_name: str
    category: str  # "General Web", "Code & Pastes", "Indian Directories & B2B", "Corporate & Legal", "Consumer Grievance & Discussion"
    query_text: str
    search_url: str
    purpose: str


def generate_manual_dorks(phone: NormalizedPhone) -> List[ManualDork]:
    """Generates a comprehensive list of targeted browser search links for the phone number."""
    if not phone.is_possible:
        return []

    e164 = phone.e164
    nat = phone.national
    dashed = phone.dashed
    digits_only = phone.digits_only
    # For Indian numbers, get raw 10-digit format
    raw_10 = digits_only[-10:] if len(digits_only) >= 10 else digits_only
    
    # Combined exact match expression
    combined_query = f'"{e164}" OR "{nat}" OR "{dashed}"'
    if phone.country_code == 91 and raw_10 != e164:
        combined_query = f'"{e164}" OR "{nat}" OR "{raw_10}" OR "{dashed}"'

    encoded_comb = quote_plus(combined_query)

    dorks: List[ManualDork] = [
        # --- General Web Search Engines ---
        ManualDork(
            engine_name="Google Search",
            category="General Web",
            query_text=combined_query,
            search_url=f"https://www.google.com/search?q={encoded_comb}",
            purpose="Discovers indexed web pages, blogs, and public forums quoting your phone number.",
        ),
        ManualDork(
            engine_name="Bing Search",
            category="General Web",
            query_text=combined_query,
            search_url=f"https://www.bing.com/search?q={encoded_comb}",
            purpose="Searches Microsoft's web index for public listings, business contacts, and profiles.",
        ),
        ManualDork(
            engine_name="DuckDuckGo",
            category="General Web",
            query_text=combined_query,
            search_url=f"https://duckduckgo.com/?q={encoded_comb}",
            purpose="Privacy-preserving web search across independent and Yahoo indexes with zero tracking.",
        ),
        ManualDork(
            engine_name="Brave Search",
            category="General Web",
            query_text=combined_query,
            search_url=f"https://search.brave.com/search?q={encoded_comb}",
            purpose="Searches Brave's independent web index with zero tracking.",
        ),
        ManualDork(
            engine_name="Yahoo Search",
            category="General Web",
            query_text=combined_query,
            search_url=f"https://search.yahoo.com/search?p={encoded_comb}",
            purpose="Legacy web index search for historical directory citations.",
        ),
        ManualDork(
            engine_name="Yandex",
            category="General Web",
            query_text=combined_query,
            search_url=f"https://yandex.com/search/?text={encoded_comb}",
            purpose="International search index providing alternate coverage.",
        ),

        # --- Code & Paste Repositories ---
        ManualDork(
            engine_name="GitHub Code Search",
            category="Code & Pastes",
            query_text=f'"{e164}" OR "{raw_10}"',
            search_url=f"https://github.com/search?type=code&q={quote_plus(f'\"{e164}\" OR \"{raw_10}\"')}",
            purpose="Detects telephone numbers accidentally hardcoded in open-source repositories and configs.",
        ),
        ManualDork(
            engine_name="Pastebin Dork (Google)",
            category="Code & Pastes",
            query_text=f'site:pastebin.com ("{e164}" OR "{raw_10}")',
            search_url=f"https://www.google.com/search?q={quote_plus(f'site:pastebin.com (\"{e164}\" OR \"{raw_10}\")')}",
            purpose="Identifies leaked pastes or database dumps containing the telephone number.",
        ),
        ManualDork(
            engine_name="Rentry.co Paste Dork",
            category="Code & Pastes",
            query_text=f'site:rentry.co ("{e164}" OR "{raw_10}")',
            search_url=f"https://www.google.com/search?q={quote_plus(f'site:rentry.co (\"{e164}\" OR \"{raw_10}\")')}",
            purpose="Finds leaks hosted on anonymous markdown pastebins.",
        ),
    ]

    # --- India-Specific Curated Targets ---
    if phone.country_code == 91 or phone.region_code == "IN":
        in_dork_expr = f'("{e164}" OR "{raw_10}" OR "{nat}")'
        dorks.extend([
            # Indian Directories & B2B
            ManualDork(
                engine_name="Justdial Directory Dork",
                category="Indian Directories & B2B",
                query_text=f'site:justdial.com {in_dork_expr}',
                search_url=f"https://www.google.com/search?q={quote_plus(f'site:justdial.com {in_dork_expr}')}",
                purpose="Checks India's largest local directory for public business/service listings.",
            ),
            ManualDork(
                engine_name="IndiaMART B2B Dork",
                category="Indian Directories & B2B",
                query_text=f'site:indiamart.com {in_dork_expr}',
                search_url=f"https://www.google.com/search?q={quote_plus(f'site:indiamart.com {in_dork_expr}')}",
                purpose="Identifies supplier, merchant, or buyer lead exposures on IndiaMART.",
            ),
            ManualDork(
                engine_name="TradeIndia B2B Dork",
                category="Indian Directories & B2B",
                query_text=f'site:tradeindia.com {in_dork_expr}',
                search_url=f"https://www.google.com/search?q={quote_plus(f'site:tradeindia.com {in_dork_expr}')}",
                purpose="Finds business contact listings on TradeIndia B2B marketplace.",
            ),
            ManualDork(
                engine_name="Sulekha Services Dork",
                category="Indian Directories & B2B",
                query_text=f'site:sulekha.com {in_dork_expr}',
                search_url=f"https://www.google.com/search?q={quote_plus(f'site:sulekha.com {in_dork_expr}')}",
                purpose="Discovers local service provider classifieds on Sulekha.",
            ),

            # Corporate & Legal Intelligence
            ManualDork(
                engine_name="Zauba Corp Company Dork",
                category="Corporate & Legal",
                query_text=f'site:zaubacorp.com {in_dork_expr}',
                search_url=f"https://www.google.com/search?q={quote_plus(f'site:zaubacorp.com {in_dork_expr}')}",
                purpose="Checks if phone is listed in Indian company master data or director DIN records.",
            ),
            ManualDork(
                engine_name="Tofler Business Intelligence Dork",
                category="Corporate & Legal",
                query_text=f'site:tofler.in {in_dork_expr}',
                search_url=f"https://www.google.com/search?q={quote_plus(f'site:tofler.in {in_dork_expr}')}",
                purpose="Searches corporate filings and registered office phone records on Tofler.",
            ),
            ManualDork(
                engine_name="MCA21 Filings Dork",
                category="Corporate & Legal",
                query_text=f'site:mca.gov.in {in_dork_expr}',
                search_url=f"https://www.google.com/search?q={quote_plus(f'site:mca.gov.in {in_dork_expr}')}",
                purpose="Detects phone mentions in Ministry of Corporate Affairs public filings.",
            ),
            ManualDork(
                engine_name="Indian Kanoon Legal Dork",
                category="Corporate & Legal",
                query_text=f'site:indiankanoon.org {in_dork_expr}',
                search_url=f"https://www.google.com/search?q={quote_plus(f'site:indiankanoon.org {in_dork_expr}')}",
                purpose="Identifies phone numbers cited in published court judgments, cause lists, or orders.",
            ),
            ManualDork(
                engine_name="The Gazette of India Dork",
                category="Corporate & Legal",
                query_text=f'site:egazette.gov.in {in_dork_expr}',
                search_url=f"https://www.google.com/search?q={quote_plus(f'site:egazette.gov.in {in_dork_expr}')}",
                purpose="Finds statutory public notices, auctions, or declarations in the Official Gazette.",
            ),

            # Consumer Grievance & Discussion
            ManualDork(
                engine_name="ConsumerComplaints.in Dork",
                category="Consumer Grievance & Discussion",
                query_text=f'site:consumercomplaints.in {in_dork_expr}',
                search_url=f"https://www.google.com/search?q={quote_plus(f'site:consumercomplaints.in {in_dork_expr}')}",
                purpose="Identifies consumer grievance posts mentioning the telephone number.",
            ),
            ManualDork(
                engine_name="MouthShut India Dork",
                category="Consumer Grievance & Discussion",
                query_text=f'site:mouthshut.com {in_dork_expr}',
                search_url=f"https://www.google.com/search?q={quote_plus(f'site:mouthshut.com {in_dork_expr}')}",
                purpose="Checks consumer review forums and customer care discussion threads.",
            ),
            ManualDork(
                engine_name="Reddit India Dork",
                category="Consumer Grievance & Discussion",
                query_text=f'(site:reddit.com/r/india OR site:reddit.com/r/developersIndia) {in_dork_expr}',
                search_url=f"https://www.google.com/search?q={quote_plus(f'(site:reddit.com/r/india OR site:reddit.com/r/developersIndia) {in_dork_expr}')}",
                purpose="Finds community discussions on telemarketing spam syndicates and leaks.",
            ),
        ])
    else:
        # Non-India International Fallbacks (US / CA etc.)
        dorks.extend([
            ManualDork(
                engine_name="FastPeopleSearch Dork",
                category="People Directories",
                query_text=f'site:fastpeoplesearch.com ("{e164}" OR "{dashed}" OR "{nat}")',
                search_url=f"https://www.google.com/search?q={quote_plus(f'site:fastpeoplesearch.com (\"{e164}\" OR \"{dashed}\" OR \"{nat}\")')}",
                purpose="Finds US profile listings on FastPeopleSearch.",
            ),
            ManualDork(
                engine_name="TruePeopleSearch Dork",
                category="People Directories",
                query_text=f'site:truepeoplesearch.com ("{e164}" OR "{dashed}" OR "{nat}")',
                search_url=f"https://www.google.com/search?q={quote_plus(f'site:truepeoplesearch.com (\"{e164}\" OR \"{dashed}\" OR \"{nat}\")')}",
                purpose="Finds US profile listings on TruePeopleSearch.",
            ),
            ManualDork(
                engine_name="Whitepages Dork",
                category="People Directories",
                query_text=f'site:whitepages.com ("{e164}" OR "{dashed}" OR "{nat}")',
                search_url=f"https://www.google.com/search?q={quote_plus(f'site:whitepages.com (\"{e164}\" OR \"{dashed}\" OR \"{nat}\")')}",
                purpose="Finds directory listings on Whitepages.",
            ),
            ManualDork(
                engine_name="Radaris Dork",
                category="People Directories",
                query_text=f'site:radaris.com ("{e164}" OR "{dashed}" OR "{nat}")',
                search_url=f"https://www.google.com/search?q={quote_plus(f'site:radaris.com (\"{e164}\" OR \"{dashed}\" OR \"{nat}\")')}",
                purpose="Checks Radaris public records aggregator.",
            ),
        ])

    return dorks
