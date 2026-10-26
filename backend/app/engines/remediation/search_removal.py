"""Search Engine De-indexing and Content Removal Workflow.
Guides users through official procedures to purge outdated cache snippets
and personal contact info from Google and Bing search indexes.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class SearchRemovalGuide:
    engine: str
    workflow_name: str
    portal_url: str
    applicability: str
    prerequisites: List[str]
    steps: List[str]
    estimated_turnaround: str


SEARCH_REMOVAL_GUIDES: List[SearchRemovalGuide] = [
    SearchRemovalGuide(
        engine="Google Search",
        workflow_name="Google Outdated Content Removal Tool",
        portal_url="https://search.google.com/search-console/remove-outdated-content",
        applicability="Use when the target data broker or website has ALREADY removed your phone number, but Google still displays it in cached search snippets.",
        prerequisites=[
            "Free Google account.",
            "The exact page URL where your number was previously listed.",
            "Confirm that visiting the page directly no longer shows your number (or gives a 404/410).",
        ],
        steps=[
            "1. Open the Outdated Content Tool at https://search.google.com/search-console/remove-outdated-content.",
            "2. Click 'New request'.",
            "3. Paste the exact URL of the webpage that was modified or removed.",
            "4. If Google detects the page is still live, enter the word or exact phone number snippet that no longer appears on the live page.",
            "5. Click 'Submit'. Google's automated crawler will re-check the page within 24 to 48 hours and refresh the search snippet.",
        ],
        estimated_turnaround="24 to 48 hours",
    ),

    SearchRemovalGuide(
        engine="Google Search",
        workflow_name="Google Select Personally Identifiable Info (PII) Removal",
        portal_url="https://support.google.com/websearch/troubleshooter/3111061",
        applicability="Use when a live webpage exposes your phone number without your consent and the website administrator is unresponsive or refuses removal.",
        prerequisites=[
            "The URL of the webpage hosting your personal phone number.",
            "The Google Search results URL that displays your listing.",
            "Screenshots showing the exposed personal contact details.",
        ],
        steps=[
            "1. Visit https://support.google.com/websearch/troubleshooter/3111061.",
            "2. Select 'Personal information, like phone numbers, addresses, or email' as the request category.",
            "3. Specify that the webmaster has not removed the content.",
            "4. Provide the search query, the search result URL, and the target webpage URL.",
            "5. Submit the request. Google human reviewers will inspect the claim and de-index the URL if it violates personal contact privacy standards.",
        ],
        estimated_turnaround="2 to 5 business days",
    ),

    SearchRemovalGuide(
        engine="Bing Search",
        workflow_name="Bing Webmaster Content Removal Tool",
        portal_url="https://www.bing.com/webmasters/tools/contentremoval",
        applicability="Use to remove outdated cache previews and broken page snippets from Bing search results.",
        prerequisites=[
            "Free Microsoft account.",
            "Page URL and outdated snippet text.",
        ],
        steps=[
            "1. Sign in to Bing Content Removal at https://www.bing.com/webmasters/tools/contentremoval.",
            "2. Click 'Remove Outdated Cache'.",
            "3. Enter the URL and the outdated phone number snippet.",
            "4. Submit. Bing typically purges the cached index entry within 48 to 72 hours.",
        ],
        estimated_turnaround="48 to 72 hours",
    ),
]


def get_search_removal_guides() -> List[SearchRemovalGuide]:
    """Returns the list of search engine removal workflow guides."""
    return SEARCH_REMOVAL_GUIDES
