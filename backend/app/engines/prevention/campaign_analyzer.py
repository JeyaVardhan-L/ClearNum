"""Campaign Analyzer for Spam Incidents.
Groups reported spam incidents into identifiable telemarketing syndicates,
detects neighbor-spoofing patterns, and categorizes common sales pitches.
"""

from dataclasses import dataclass
from typing import List, Dict, Any
import re
from collections import defaultdict
from backend.app.engines.prevention.incident_tracker import SpamIncidentRecord

CAMPAIGN_TOPICS = {
    "Auto Warranty": [r"warranty", r"vehicle", r"car coverage", r"service contract"],
    "Health Insurance": [r"health", r"medicare", r"insurance", r"affordable care", r"open enrollment"],
    "Debt Relief & Loans": [r"loan", r"debt", r"credit card", r"forgiveness", r"interest rate", r"refinance"],
    "Solar & Home Improvement": [r"solar", r"roof", r"energy", r"home improvement", r"windows"],
    "Phishing & Package Alerts": [r"package", r"usps", r"fedex", r"delivery", r"bank", r"suspended", r"urgent"],
    "Impersonal Robocalls": [r"press 1", r"automated message", r"recorded line", r"agent"],
}


@dataclass
class CampaignGroup:
    campaign_name: str
    incident_count: int
    sender_numbers: List[str]
    channels: List[str]
    sample_pitches: List[str]
    spoof_percentage: float


def analyze_spam_campaigns(incidents: List[SpamIncidentRecord]) -> List[CampaignGroup]:
    """Analyzes a collection of spam incidents and clusters them by campaign pitch and sender patterns."""
    if not incidents:
        return []

    clusters: Dict[str, List[SpamIncidentRecord]] = defaultdict(list)

    for inc in incidents:
        matched_topic = None
        pitch_lower = inc.campaign_summary.lower()

        for topic, patterns in CAMPAIGN_TOPICS.items():
            if any(re.search(pat, pitch_lower) for pat in patterns):
                matched_topic = topic
                break

        if not matched_topic:
            # Check by channel / category
            if inc.category == "ROBOCALL":
                matched_topic = "Uncategorized Robocall Syndicate"
            elif inc.category == "MARKETING_SMS":
                matched_topic = "Uncategorized SMS Promotional Blast"
            else:
                matched_topic = "General Unsolicited Telemarketing"

        clusters[matched_topic].append(inc)

    results: List[CampaignGroup] = []
    for topic, group_incidents in clusters.items():
        senders = list(dict.fromkeys(i.sender_number for i in group_incidents if i.sender_number))
        channels = list(dict.fromkeys(i.channel for i in group_incidents))
        samples = [i.campaign_summary for i in group_incidents if i.campaign_summary][:3]
        spoofs = sum(1 for i in group_incidents if i.spoof_suspected)
        spoof_pct = (spoofs / len(group_incidents)) * 100.0 if group_incidents else 0.0

        results.append(CampaignGroup(
            campaign_name=topic,
            incident_count=len(group_incidents),
            sender_numbers=senders,
            channels=channels,
            sample_pitches=samples,
            spoof_percentage=round(spoof_pct, 1),
        ))

    return sorted(results, key=lambda g: g.incident_count, reverse=True)
