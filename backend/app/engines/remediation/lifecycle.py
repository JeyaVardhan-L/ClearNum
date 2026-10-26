"""Truthful Lifecycle State Machine for Remediation Actions.
Enforces verifiable, evidence-based transitions and prevents fraudulent or premature
claims of successful removal.
"""

from enum import Enum
from typing import Set, Dict, Optional


class ActionState(str, Enum):
    DISCOVERED = "DISCOVERED"
    VERIFIED = "VERIFIED"
    ACTION_AVAILABLE = "ACTION_AVAILABLE"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    VERIFIED_REMOVED = "VERIFIED_REMOVED"
    
    # Side / Terminal States
    REJECTED = "REJECTED"                      # Marked as false-positive match by user
    MANUAL_ACTION_REQUIRED = "MANUAL_ACTION_REQUIRED"  # Requires phone call, physical mail, ID upload
    PENDING = "PENDING"                        # Waiting for standard processing window (24-72h)
    FAILED = "FAILED"                          # Request was explicitly denied or form failed
    UNABLE_TO_VERIFY = "UNABLE_TO_VERIFY"      # Site blocked by bot protection or ambiguous


# Valid transition graph
PERMITTED_TRANSITIONS: Dict[ActionState, Set[ActionState]] = {
    ActionState.DISCOVERED: {
        ActionState.VERIFIED,
        ActionState.REJECTED,
    },
    ActionState.VERIFIED: {
        ActionState.ACTION_AVAILABLE,
        ActionState.MANUAL_ACTION_REQUIRED,
        ActionState.REJECTED,
    },
    ActionState.ACTION_AVAILABLE: {
        ActionState.SUBMITTED,
        ActionState.MANUAL_ACTION_REQUIRED,
        ActionState.REJECTED,
    },
    ActionState.SUBMITTED: {
        ActionState.ACKNOWLEDGED,
        ActionState.PENDING,
        ActionState.VERIFIED_REMOVED,  # When verified by rescan
        ActionState.FAILED,
        ActionState.UNABLE_TO_VERIFY,
        ActionState.REJECTED,
    },
    ActionState.ACKNOWLEDGED: {
        ActionState.PENDING,
        ActionState.VERIFIED_REMOVED,  # When verified by rescan
        ActionState.FAILED,
        ActionState.UNABLE_TO_VERIFY,
        ActionState.REJECTED,
    },
    ActionState.PENDING: {
        ActionState.VERIFIED_REMOVED,  # When verified by rescan
        ActionState.FAILED,
        ActionState.UNABLE_TO_VERIFY,
        ActionState.SUBMITTED,        # If re-submitted after timeout
        ActionState.REJECTED,
    },
    ActionState.MANUAL_ACTION_REQUIRED: {
        ActionState.SUBMITTED,
        ActionState.FAILED,
        ActionState.REJECTED,
    },
    ActionState.FAILED: {
        ActionState.SUBMITTED,        # Retry attempt
        ActionState.MANUAL_ACTION_REQUIRED,
        ActionState.REJECTED,
    },
    ActionState.UNABLE_TO_VERIFY: {
        ActionState.VERIFIED_REMOVED,  # Successful later rescan
        ActionState.FAILED,
        ActionState.SUBMITTED,        # Retry attempt
        ActionState.REJECTED,
    },
    ActionState.VERIFIED_REMOVED: {
        # If number reappears later, it can be re-opened
        ActionState.DISCOVERED,
    },
    ActionState.REJECTED: {
        # Can be reopened if user re-evaluates
        ActionState.DISCOVERED,
        ActionState.VERIFIED,
    },
}


class InvalidStateTransitionError(Exception):
    """Raised when an action attempts an unsupported state change."""
    pass


def validate_transition(current_state: ActionState | str, next_state: ActionState | str) -> bool:
    """Validates whether transitioning from current_state to next_state is legitimate."""
    curr = ActionState(current_state) if isinstance(current_state, str) else current_state
    nxt = ActionState(next_state) if isinstance(next_state, str) else next_state

    valid_next = PERMITTED_TRANSITIONS.get(curr, set())
    if nxt not in valid_next:
        raise InvalidStateTransitionError(
            f"Invalid lifecycle transition from '{curr.value}' to '{nxt.value}'. "
            f"Allowed next states: {[s.value for s in valid_next]}"
        )
    return True


def get_state_color_token(state: ActionState | str) -> str:
    """Returns the CSS token/color class corresponding to the truthful lifecycle state."""
    s = ActionState(state) if isinstance(state, str) else state
    if s == ActionState.VERIFIED_REMOVED:
        return "text-emerald-400 bg-emerald-950/40 border-emerald-800"
    elif s in (ActionState.SUBMITTED, ActionState.ACKNOWLEDGED, ActionState.PENDING):
        return "text-cyan-400 bg-cyan-950/40 border-cyan-800"
    elif s in (ActionState.ACTION_AVAILABLE, ActionState.VERIFIED):
        return "text-amber-400 bg-amber-950/40 border-amber-800"
    elif s in (ActionState.FAILED, ActionState.UNABLE_TO_VERIFY):
        return "text-rose-400 bg-rose-950/40 border-rose-800"
    elif s == ActionState.REJECTED:
        return "text-slate-400 bg-slate-900 border-slate-700"
    return "text-blue-400 bg-blue-950/40 border-blue-800"
