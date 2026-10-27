"""Tests for truthful remediation lifecycle state transitions and evidence rules."""

import pytest
from backend.app.engines.remediation.lifecycle import (
    ActionState,
    validate_transition,
    InvalidStateTransitionError,
    normalize_state,
    EVIDENCE_RULES,
)


def test_valid_sequential_lifecycle_truthful_states():
    """Verify standard progression through the truthful lifecycle state machine."""
    # Step 1: Discovery to user review
    assert validate_transition(ActionState.DISCOVERED, ActionState.AWAITING_USER_REVIEW) is True
    # Step 2: User review to confirmed exposure
    assert validate_transition(ActionState.AWAITING_USER_REVIEW, ActionState.CONFIRMED_EXPOSURE) is True
    # Step 3: Confirmed exposure to awaiting approval
    assert validate_transition(ActionState.CONFIRMED_EXPOSURE, ActionState.AWAITING_USER_APPROVAL) is True
    # Step 4: Approval to request prepared
    assert validate_transition(ActionState.AWAITING_USER_APPROVAL, ActionState.REQUEST_PREPARED) is True
    # Step 5: Request prepared to submitted
    assert validate_transition(ActionState.REQUEST_PREPARED, ActionState.SUBMITTED) is True
    # Step 6: Submitted to acknowledged
    assert validate_transition(ActionState.SUBMITTED, ActionState.ACKNOWLEDGED) is True
    # Step 7: Acknowledged to awaiting verification
    assert validate_transition(ActionState.ACKNOWLEDGED, ActionState.AWAITING_VERIFICATION) is True
    # Step 8: Rescan shows no longer visible at URL
    assert validate_transition(ActionState.AWAITING_VERIFICATION, ActionState.NO_LONGER_VISIBLE_AT_CHECKED_URL) is True
    # Step 9: Source confirms permanent backend removal
    assert validate_transition(ActionState.NO_LONGER_VISIBLE_AT_CHECKED_URL, ActionState.SOURCE_CONFIRMED_REMOVAL) is True
    # Step 10: If listing reappears in future audit
    assert validate_transition(ActionState.SOURCE_CONFIRMED_REMOVAL, ActionState.REAPPEARED) is True


def test_valid_rejection_from_discovered_and_review():
    assert validate_transition(ActionState.DISCOVERED, ActionState.REJECTED) is True
    assert validate_transition(ActionState.AWAITING_USER_REVIEW, ActionState.REJECTED) is True


def test_invalid_premature_removal_claim():
    # Direct leap from DISCOVERED to SOURCE_CONFIRMED_REMOVAL without submission or review
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(ActionState.DISCOVERED, ActionState.SOURCE_CONFIRMED_REMOVAL)


def test_invalid_arbitrary_transition():
    # Cannot jump from AWAITING_USER_APPROVAL directly to ACKNOWLEDGED without SUBMITTED
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(ActionState.AWAITING_USER_APPROVAL, ActionState.ACKNOWLEDGED)


def test_legacy_state_normalization_backwards_compatible():
    assert normalize_state("VERIFIED") == ActionState.CONFIRMED_EXPOSURE
    assert normalize_state("ACTION_AVAILABLE") == ActionState.AWAITING_USER_APPROVAL
    assert normalize_state("PENDING") == ActionState.AWAITING_VERIFICATION
    assert normalize_state("VERIFIED_REMOVED") == ActionState.NO_LONGER_VISIBLE_AT_CHECKED_URL
    assert normalize_state("UNABLE_TO_VERIFY") == ActionState.INACCESSIBLE_OR_INCONCLUSIVE
    assert normalize_state("FAILED") == ActionState.STILL_VISIBLE


def test_evidence_rules_exist_for_critical_states():
    assert ActionState.CONFIRMED_EXPOSURE in EVIDENCE_RULES
    assert ActionState.SUBMITTED in EVIDENCE_RULES
    assert ActionState.ACKNOWLEDGED in EVIDENCE_RULES
    assert ActionState.NO_LONGER_VISIBLE_AT_CHECKED_URL in EVIDENCE_RULES
    assert ActionState.SEARCH_RESULT_DELISTED in EVIDENCE_RULES
    assert ActionState.SOURCE_CONFIRMED_REMOVAL in EVIDENCE_RULES
    assert ActionState.STILL_VISIBLE in EVIDENCE_RULES
    assert ActionState.INACCESSIBLE_OR_INCONCLUSIVE in EVIDENCE_RULES
    assert ActionState.REAPPEARED in EVIDENCE_RULES


def test_url_disappearance_distinct_from_source_deletion():
    """Verify that URL absence is strictly distinguished from affirmative source backend deletion."""
    assert ActionState.NO_LONGER_VISIBLE_AT_CHECKED_URL != ActionState.SOURCE_CONFIRMED_REMOVAL
    url_absence_rule = EVIDENCE_RULES[ActionState.NO_LONGER_VISIBLE_AT_CHECKED_URL]
    source_del_rule = EVIDENCE_RULES[ActionState.SOURCE_CONFIRMED_REMOVAL]
    assert url_absence_rule.required_evidence_type == "HTTP_ABSENCE_CHECK"
    assert source_del_rule.required_evidence_type == "STATUTORY_DELETION_RECEIPT"
    assert "404" in url_absence_rule.description or "absence" in url_absence_rule.description.lower()
    assert "deletion" in source_del_rule.description.lower() or "receipt" in source_del_rule.description.lower()


def test_search_delisting_distinct_from_source_removal():
    """Search engine delisting (Google/Bing) must never be reported as source removal."""
    delist_rule = EVIDENCE_RULES[ActionState.SEARCH_RESULT_DELISTED]
    source_rule = EVIDENCE_RULES[ActionState.SOURCE_CONFIRMED_REMOVAL]
    assert delist_rule.required_evidence_type == "SEARCH_INDEX_AUDIT"
    assert source_rule.required_evidence_type == "STATUTORY_DELETION_RECEIPT"
    assert ActionState.SEARCH_RESULT_DELISTED != ActionState.SOURCE_CONFIRMED_REMOVAL



@pytest.mark.parametrize("source_state,invalid_target", [
    (ActionState.DISCOVERED, ActionState.SUBMITTED),
    (ActionState.DISCOVERED, ActionState.SOURCE_CONFIRMED_REMOVAL),
    (ActionState.AWAITING_USER_APPROVAL, ActionState.NO_LONGER_VISIBLE_AT_CHECKED_URL),
    (ActionState.CONFIRMED_EXPOSURE, ActionState.SOURCE_CONFIRMED_REMOVAL),
    (ActionState.NO_LONGER_VISIBLE_AT_CHECKED_URL, ActionState.SUBMITTED),
])
def test_forbidden_transitions_rejected(source_state, invalid_target):
    """Ensure invalid transitions are rejected unconditionally by state machine."""
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(source_state, invalid_target)


def test_database_migration_from_legacy_schema(tmp_path):
    """Simulate a legacy SQLite database containing deprecated status values and verify
    that init_db migrates all records to truthful state machine values."""
    import sqlite3
    from backend.app.core.database import init_db

    db_file = tmp_path / "legacy_test.db"
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    # Create tables with legacy schema
    cur.execute("""
        CREATE TABLE exposures (id TEXT PRIMARY KEY, identity_hmac TEXT, url TEXT, domain TEXT, title TEXT, match_type TEXT, confidence REAL, snippet TEXT, discovered_at TEXT, last_checked_at TEXT);
    """)
    cur.execute("""
        CREATE TABLE remediation_actions (id TEXT PRIMARY KEY, exposure_id TEXT, identity_hmac TEXT, source_id TEXT, status TEXT, official_url TEXT, submission_ref TEXT, notes TEXT, verified_at TEXT, updated_at TEXT);
    """)
    legacy_records = [
        ("act-1", "exp-1", "hmac-1", "VERIFIED"),
        ("act-2", "exp-2", "hmac-1", "ACTION_AVAILABLE"),
        ("act-3", "exp-3", "hmac-1", "PENDING"),
        ("act-4", "exp-4", "hmac-1", "VERIFIED_REMOVED"),
        ("act-5", "exp-5", "hmac-1", "UNABLE_TO_VERIFY"),
        ("act-6", "exp-6", "hmac-1", "FAILED"),
    ]
    for act_id, exp_id, hmac, st in legacy_records:
        cur.execute("INSERT INTO remediation_actions (id, exposure_id, identity_hmac, status) VALUES (?, ?, ?, ?)", (act_id, exp_id, hmac, st))
    conn.commit()
    conn.close()

    # Run init_db on the legacy database
    init_db(db_file)

    conn2 = sqlite3.connect(str(db_file))
    cur2 = conn2.cursor()
    cur2.execute("SELECT id, status FROM remediation_actions ORDER BY id")
    rows = dict(cur2.fetchall())
    conn2.close()

    assert rows["act-1"] == "CONFIRMED_EXPOSURE"
    assert rows["act-2"] == "AWAITING_USER_APPROVAL"
    assert rows["act-3"] == "AWAITING_VERIFICATION"
    assert rows["act-4"] == "NO_LONGER_VISIBLE_AT_CHECKED_URL"
    assert rows["act-5"] == "INACCESSIBLE_OR_INCONCLUSIVE"
    assert rows["act-6"] == "STILL_VISIBLE"
