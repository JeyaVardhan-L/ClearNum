"""Prevention and Exposure Metrics Engine.
Computes real, un-fabricated statistics on exposure lifecycle states,
removal effectiveness, and unwanted contact trends over time.
"""

from dataclasses import dataclass
from typing import Dict, Any, List
from backend.app.core.database import get_db_connection


@dataclass
class ExposureMetrics:
    total_exposures: int
    verified_removed: int
    pending_actions: int
    submitted_actions: int
    action_available: int
    rejected_matches: int
    active_subscriptions: int
    total_spam_incidents: int
    removal_success_rate: float
    exposure_by_source: Dict[str, int]
    incidents_by_category: Dict[str, int]


def calculate_metrics(identity_hmac: str) -> ExposureMetrics:
    """Calculates factual metrics for a given identity HMAC."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Total exposures
    cursor.execute("SELECT COUNT(*) as count FROM exposures WHERE identity_hmac = ?", (identity_hmac,))
    total_exposures = cursor.fetchone()["count"]

    # Exposures by source domain
    cursor.execute("""
        SELECT domain, COUNT(*) as count
        FROM exposures
        WHERE identity_hmac = ?
        GROUP BY domain
    """, (identity_hmac,))
    exposure_by_source = {r["domain"]: r["count"] for r in cursor.fetchall()}

    # Remediation actions by status
    cursor.execute("""
        SELECT status, COUNT(*) as count
        FROM remediation_actions
        WHERE identity_hmac = ?
        GROUP BY status
    """, (identity_hmac,))
    status_counts = {r["status"]: r["count"] for r in cursor.fetchall()}

    verified_removed = (
        status_counts.get("NO_LONGER_VISIBLE_AT_CHECKED_URL", 0)
        + status_counts.get("SOURCE_CONFIRMED_REMOVAL", 0)
        + status_counts.get("SEARCH_RESULT_DELISTED", 0)
        + status_counts.get("VERIFIED_REMOVED", 0)
    )
    submitted_actions = status_counts.get("SUBMITTED", 0) + status_counts.get("ACKNOWLEDGED", 0)
    pending_actions = status_counts.get("AWAITING_VERIFICATION", 0) + status_counts.get("PENDING", 0)
    action_available = (
        status_counts.get("AWAITING_USER_APPROVAL", 0)
        + status_counts.get("REQUEST_PREPARED", 0)
        + status_counts.get("CONFIRMED_EXPOSURE", 0)
        + status_counts.get("ACTION_AVAILABLE", 0)
        + status_counts.get("VERIFIED", 0)
    )
    rejected_matches = status_counts.get("REJECTED", 0)

    # Subscriptions
    cursor.execute("SELECT COUNT(*) as count FROM subscriptions WHERE identity_hmac = ?", (identity_hmac,))
    active_subscriptions = cursor.fetchone()["count"]

    # Spam incidents
    cursor.execute("SELECT COUNT(*) as count FROM spam_incidents WHERE identity_hmac = ?", (identity_hmac,))
    total_spam_incidents = cursor.fetchone()["count"]

    cursor.execute("""
        SELECT category, COUNT(*) as count
        FROM spam_incidents
        WHERE identity_hmac = ?
        GROUP BY category
    """, (identity_hmac,))
    incidents_by_category = {r["category"]: r["count"] for r in cursor.fetchall()}

    conn.close()

    # Factual success rate calculation
    actionable_total = total_exposures - rejected_matches
    if actionable_total > 0:
        success_rate = round((verified_removed / actionable_total) * 100.0, 1)
    else:
        success_rate = 0.0

    return ExposureMetrics(
        total_exposures=total_exposures,
        verified_removed=verified_removed,
        pending_actions=pending_actions,
        submitted_actions=submitted_actions,
        action_available=action_available,
        rejected_matches=rejected_matches,
        active_subscriptions=active_subscriptions,
        total_spam_incidents=total_spam_incidents,
        removal_success_rate=success_rate,
        exposure_by_source=exposure_by_source,
        incidents_by_category=incidents_by_category,
    )
