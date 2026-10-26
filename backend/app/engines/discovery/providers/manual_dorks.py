"""Manual Dorking Generator.
Produces pre-computed, URL-encoded search links across Google, Bing, Brave, Yahoo,
Yandex, GitHub, Pastebin, and specialized people directories for 1-click execution.
"""

from dataclasses import dataclass
from typing import List
from urllib.parse import quote_plus
from backend.app.engines.discovery.normalizer import NormalizedPhone


@dataclass
class ManualDork:
    engine_name: str
    category: str  # "General Web", "Code & Pastes", "People Directories", "Business & Forums"
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
    
    # Combined exact match expression
    combined_query = f'"{e164}" OR "{nat}" OR "{dashed}"'
    encoded_comb = quote_plus(combined_query)
    encoded_e164 = quote_plus(f'"{e164}"')

    dorks: List[ManualDork] = [
        # --- General Web Search Engines ---
        ManualDork(
            engine_name="Google Search",
            category="General Web",
            query_text=combined_query,
            search_url=f"https://www.google.com/search?q={encoded_comb}",
            purpose="Discovers indexed web pages, blogs, and forums quoting the number.",
        ),
        ManualDork(
            engine_name="Bing Search",
            category="General Web",
            query_text=combined_query,
            search_url=f"https://www.bing.com/search?q={encoded_comb}",
            purpose="Searches Microsoft's web index for public listings and social profiles.",
        ),
        ManualDork(
            engine_name="DuckDuckGo",
            category="General Web",
            query_text=combined_query,
            search_url=f"https://duckduckgo.com/?q={encoded_comb}",
            purpose="Privacy-preserving web search across independent and Yahoo indexes.",
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
            purpose="International and Eastern European search index.",
        ),

        # --- Code & Paste Repositories ---
        ManualDork(
            engine_name="GitHub Code Search",
            category="Code & Pastes",
            query_text=f'"{e164}" OR "{dashed}"',
            search_url=f"https://github.com/search?type=code&q={quote_plus(f'\"{e164}\" OR \"{dashed}\"')}",
            purpose="Detects numbers accidentally hardcoded in open-source repositories and configs.",
        ),
        ManualDork(
            engine_name="Pastebin Dork (Google)",
            category="Code & Pastes",
            query_text=f'site:pastebin.com ("{e164}" OR "{dashed}")',
            search_url=f"https://www.google.com/search?q={quote_plus(f'site:pastebin.com (\"{e164}\" OR \"{dashed}\")')}",
            purpose="Identifies leaked pastes or scrapers containing the telephone number.",
        ),

        # --- Data Brokers & People Directories ---
        ManualDork(
            engine_name="FastPeopleSearch Dork",
            category="People Directories",
            query_text=f'site:fastpeoplesearch.com ("{e164}" OR "{dashed}" OR "{nat}")',
            search_url=f"https://www.google.com/search?q={quote_plus(f'site:fastpeoplesearch.com (\"{e164}\" OR \"{dashed}\" OR \"{nat}\")')}",
            purpose="Discovers your public profile directly on FastPeopleSearch.",
        ),
        ManualDork(
            engine_name="TruePeopleSearch Dork",
            category="People Directories",
            query_text=f'site:truepeoplesearch.com ("{dashed}" OR "{nat}")',
            search_url=f"https://www.google.com/search?q={quote_plus(f'site:truepeoplesearch.com (\"{dashed}\" OR \"{nat}\")')}",
            purpose="Finds indexed TruePeopleSearch records linked to your number.",
        ),
        ManualDork(
            engine_name="Whitepages Dork",
            category="People Directories",
            query_text=f'site:whitepages.com ("{dashed}" OR "{nat}")',
            search_url=f"https://www.google.com/search?q={quote_plus(f'site:whitepages.com (\"{dashed}\" OR \"{nat}\")')}",
            purpose="Finds residential and reverse-phone Whitepages listings.",
        ),
        ManualDork(
            engine_name="Radaris Dork",
            category="People Directories",
            query_text=f'site:radaris.com ("{dashed}" OR "{e164}")',
            search_url=f"https://www.google.com/search?q={quote_plus(f'site:radaris.com (\"{dashed}\" OR \"{e164}\")')}",
            purpose="Identifies background check profile records on Radaris.",
        ),
        ManualDork(
            engine_name="Spokeo Dork",
            category="People Directories",
            query_text=f'site:spokeo.com ("{dashed}" OR "{e164}")',
            search_url=f"https://www.google.com/search?q={quote_plus(f'site:spokeo.com (\"{dashed}\" OR \"{e164}\")')}",
            purpose="Discovers reverse phone lookup profiles on Spokeo.",
        ),

        # --- Business & Classifieds ---
        ManualDork(
            engine_name="Craigslist / Classifieds Dork",
            category="Business & Forums",
            query_text=f'site:craigslist.org ("{dashed}" OR "{nat}")',
            search_url=f"https://www.google.com/search?q={quote_plus(f'site:craigslist.org (\"{dashed}\" OR \"{nat}\")')}",
            purpose="Discovers old classified advertisements containing your phone number.",
        ),
        ManualDork(
            engine_name="Yelp Business Listings",
            category="Business & Forums",
            query_text=f'site:yelp.com ("{dashed}" OR "{nat}")',
            search_url=f"https://www.google.com/search?q={quote_plus(f'site:yelp.com (\"{dashed}\" OR \"{nat}\")')}",
            purpose="Detects if your personal number is listed as a commercial business line.",
        ),
    ]

    return dorks
