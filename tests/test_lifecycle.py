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
