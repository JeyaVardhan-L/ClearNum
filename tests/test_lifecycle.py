"""Tests for truthful remediation lifecycle state transitions."""

import pytest
from backend.app.engines.remediation.lifecycle import (
    ActionState,
    validate_transition,
    InvalidStateTransitionError,
)


def test_valid_sequential_lifecycle():
    assert validate_transition(ActionState.DISCOVERED, ActionState.VERIFIED) is True
    assert validate_transition(ActionState.VERIFIED, ActionState.ACTION_AVAILABLE) is True
    assert validate_transition(ActionState.ACTION_AVAILABLE, ActionState.SUBMITTED) is True
    assert validate_transition(ActionState.SUBMITTED, ActionState.ACKNOWLEDGED) is True
    assert validate_transition(ActionState.ACKNOWLEDGED, ActionState.VERIFIED_REMOVED) is True


def test_valid_rejection_from_discovered():
    assert validate_transition(ActionState.DISCOVERED, ActionState.REJECTED) is True


def test_invalid_premature_removal_claim():
    # Direct leap from DISCOVERED to VERIFIED_REMOVED without evidence or submission
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(ActionState.DISCOVERED, ActionState.VERIFIED_REMOVED)


def test_invalid_arbitrary_transition():
    # Cannot jump from ACTION_AVAILABLE directly to ACKNOWLEDGED without SUBMITTED
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(ActionState.ACTION_AVAILABLE, ActionState.ACKNOWLEDGED)
