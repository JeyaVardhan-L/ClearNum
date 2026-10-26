"""Spam Incident Tracker.
Records user-reported unwanted telemarketing calls and spam SMS,
including caller ID spoof suspicion and campaign keywords.
"""

from dataclasses import dataclass
from typing import List, Optional
import uuid
from backend.app.core.database import get_db_connection, utc_now_iso


@dataclass
class SpamIncidentRecord:
    id: str
    identity_hmac: str
    sender_number: str
    channel: str  # "CALL", "SMS", "WHATSAPP"
    category: str  # "ROBOCALL", "LIVE_AGENT", "MARKETING_SMS", "PHISHING"
    spoof_suspected: bool
    campaign_summary: str
    reported_at: str


def record_spam_incident(
    identity_hmac: str,
    sender_number: str,
    channel: str = "CALL",
    category: str = "ROBOCALL",
    spoof_suspected: bool = False,
    campaign_summary: str = "",
) -> SpamIncidentRecord:
    """Inserts a new spam incident into local database."""
    incident_id = str(uuid.uuid4())
    now_iso = utc_now_iso()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO spam_incidents (
            id, identity_hmac, sender_number, channel, category, spoof_suspected, campaign_summary, reported_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        incident_id,
        identity_hmac,
        sender_number.strip(),
        channel.upper(),
        category.upper(),
        1 if spoof_suspected else 0,
        campaign_summary.strip(),
        now_iso,
    ))
    conn.commit()
    conn.close()

    return SpamIncidentRecord(
        id=incident_id,
        identity_hmac=identity_hmac,
        sender_number=sender_number.strip(),
        channel=channel.upper(),
        category=category.upper(),
        spoof_suspected=spoof_suspected,
        campaign_summary=campaign_summary.strip(),
        reported_at=now_iso,
    )


def list_spam_incidents(identity_hmac: str) -> List[SpamIncidentRecord]:
    """Retrieves all spam incident records for a given identity."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, identity_hmac, sender_number, channel, category, spoof_suspected, campaign_summary, reported_at
        FROM spam_incidents
        WHERE identity_hmac = ?
        ORDER BY reported_at DESC
    """, (identity_hmac,))
    rows = cursor.fetchall()
    conn.close()

    return [
        SpamIncidentRecord(
            id=r["id"],
            identity_hmac=r["identity_hmac"],
            sender_number=r["sender_number"],
            channel=r["channel"],
            category=r["category"],
            spoof_suspected=bool(r["spoof_suspected"]),
            campaign_summary=r["campaign_summary"] or "",
            reported_at=r["reported_at"],
        )
        for r in rows
    ]
