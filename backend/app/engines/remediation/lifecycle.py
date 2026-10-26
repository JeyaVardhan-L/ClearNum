"""Truthful Lifecycle State Machine for Remediation Actions.
Enforces verifiable, evidence-based transitions and strictly forbids fraudulent,
simulated, or premature claims of data removal.

Distinguishes absence from a single URL fetch from affirmative database removal confirmed by the source.
"""

from enum import Enum
from typing import Set, Dict, Optional
from dataclasses import dataclass


class ActionState(str, Enum):
    # Discovery & User Review
    DISCOVERED = "DISCOVERED"
    AWAITING_USER_REVIEW = "AWAITING_USER_REVIEW"
    CONFIRMED_EXPOSURE = "CONFIRMED_EXPOSURE"
    REJECTED = "REJECTED"                      # Marked as false-positive match by user

    # Remediation Workflow
    AWAITING_USER_APPROVAL = "AWAITING_USER_APPROVAL"
    REQUEST_PREPARED = "REQUEST_PREPARED"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    AWAITING_VERIFICATION = "AWAITING_VERIFICATION"

    # Truthful Verification & Outcome States
    NO_LONGER_VISIBLE_AT_CHECKED_URL = "NO_LONGER_VISIBLE_AT_CHECKED_URL"  # HTTP 404/410 or content scrubbed at URL
    SEARCH_RESULT_DELISTED = "SEARCH_RESULT_DELISTED"                      # Google/Bing PII search index removal
    SOURCE_CONFIRMED_REMOVAL = "SOURCE_CONFIRMED_REMOVAL"                  # Broker issued deletion receipt/code
    STILL_VISIBLE = "STILL_VISIBLE"                                        # Target still displays telephone number
    INACCESSIBLE_OR_INCONCLUSIVE = "INACCESSIBLE_OR_INCONCLUSIVE"          # 403, Cloudflare, anti-bot challenge
    REAPPEARED = "REAPPEARED"                                              # Was not visible, but reappeared in new audit

    # Backward-compatibility legacy state aliases
    VERIFIED = "VERIFIED"
    ACTION_AVAILABLE = "ACTION_AVAILABLE"
    PENDING = "PENDING"
    VERIFIED_REMOVED = "VERIFIED_REMOVED"
    UNABLE_TO_VERIFY = "UNABLE_TO_VERIFY"
    FAILED = "FAILED"
    MANUAL_ACTION_REQUIRED = "MANUAL_ACTION_REQUIRED"


LEGACY_STATE_MAPPINGS: Dict[str, ActionState] = {
    "VERIFIED": ActionState.CONFIRMED_EXPOSURE,
    "ACTION_AVAILABLE": ActionState.AWAITING_USER_APPROVAL,
    "PENDING": ActionState.AWAITING_VERIFICATION,
    "VERIFIED_REMOVED": ActionState.NO_LONGER_VISIBLE_AT_CHECKED_URL,
    "UNABLE_TO_VERIFY": ActionState.INACCESSIBLE_OR_INCONCLUSIVE,
    "FAILED": ActionState.STILL_VISIBLE,
    "MANUAL_ACTION_REQUIRED": ActionState.AWAITING_USER_APPROVAL,
}


def normalize_state(state: ActionState | str) -> ActionState:
    """Normalizes legacy action states into canonical truthful states."""
    val = state.value if isinstance(state, ActionState) else str(state)
    if val in LEGACY_STATE_MAPPINGS:
        return LEGACY_STATE_MAPPINGS[val]
    try:
        return ActionState(val)
    except ValueError:
        raise InvalidStateTransitionError(f"Unknown or unsupported lifecycle state '{val}'")


# Valid transition graph
PERMITTED_TRANSITIONS: Dict[ActionState, Set[ActionState]] = {
    ActionState.DISCOVERED: {
        ActionState.AWAITING_USER_REVIEW,
        ActionState.CONFIRMED_EXPOSURE,
        ActionState.REJECTED,
    },
    ActionState.AWAITING_USER_REVIEW: {
        ActionState.CONFIRMED_EXPOSURE,
        ActionState.REJECTED,
    },
    ActionState.CONFIRMED_EXPOSURE: {
        ActionState.AWAITING_USER_APPROVAL,
        ActionState.REQUEST_PREPARED,
        ActionState.SUBMITTED,
        ActionState.REJECTED,
        ActionState.STILL_VISIBLE,
    },
    ActionState.AWAITING_USER_APPROVAL: {
        ActionState.REQUEST_PREPARED,
        ActionState.SUBMITTED,
        ActionState.REJECTED,
    },
    ActionState.REQUEST_PREPARED: {
        ActionState.SUBMITTED,
        ActionState.AWAITING_USER_APPROVAL,
        ActionState.REJECTED,
    },
    ActionState.SUBMITTED: {
        ActionState.ACKNOWLEDGED,
        ActionState.AWAITING_VERIFICATION,
        ActionState.NO_LONGER_VISIBLE_AT_CHECKED_URL,
        ActionState.SOURCE_CONFIRMED_REMOVAL,
        ActionState.STILL_VISIBLE,
        ActionState.INACCESSIBLE_OR_INCONCLUSIVE,
        ActionState.REJECTED,
    },
    ActionState.ACKNOWLEDGED: {
        ActionState.AWAITING_VERIFICATION,
        ActionState.NO_LONGER_VISIBLE_AT_CHECKED_URL,
        ActionState.SOURCE_CONFIRMED_REMOVAL,
        ActionState.STILL_VISIBLE,
        ActionState.INACCESSIBLE_OR_INCONCLUSIVE,
        ActionState.REJECTED,
    },
    ActionState.AWAITING_VERIFICATION: {
        ActionState.NO_LONGER_VISIBLE_AT_CHECKED_URL,
        ActionState.SEARCH_RESULT_DELISTED,
        ActionState.SOURCE_CONFIRMED_REMOVAL,
        ActionState.STILL_VISIBLE,
        ActionState.INACCESSIBLE_OR_INCONCLUSIVE,
        ActionState.SUBMITTED,
        ActionState.REJECTED,
    },
    ActionState.STILL_VISIBLE: {
        ActionState.SUBMITTED,
        ActionState.REQUEST_PREPARED,
        ActionState.SEARCH_RESULT_DELISTED,
        ActionState.AWAITING_VERIFICATION,
        ActionState.NO_LONGER_VISIBLE_AT_CHECKED_URL,
        ActionState.REJECTED,
    },
    ActionState.INACCESSIBLE_OR_INCONCLUSIVE: {
        ActionState.AWAITING_VERIFICATION,
        ActionState.NO_LONGER_VISIBLE_AT_CHECKED_URL,
        ActionState.STILL_VISIBLE,
        ActionState.SUBMITTED,
        ActionState.REJECTED,
    },
    ActionState.NO_LONGER_VISIBLE_AT_CHECKED_URL: {
        ActionState.SEARCH_RESULT_DELISTED,
        ActionState.SOURCE_CONFIRMED_REMOVAL,
        ActionState.REAPPEARED,
    },
    ActionState.SEARCH_RESULT_DELISTED: {
        ActionState.SOURCE_CONFIRMED_REMOVAL,
        ActionState.REAPPEARED,
    },
    ActionState.SOURCE_CONFIRMED_REMOVAL: {
        # Can only reopen if number affirmatively reappears in future audit
        ActionState.REAPPEARED,
    },
    ActionState.REAPPEARED: {
        ActionState.CONFIRMED_EXPOSURE,
        ActionState.AWAITING_USER_APPROVAL,
        ActionState.REQUEST_PREPARED,
        ActionState.SUBMITTED,
    },
    ActionState.REJECTED: {
        ActionState.DISCOVERED,
        ActionState.AWAITING_USER_REVIEW,
        ActionState.CONFIRMED_EXPOSURE,
    },
}


class InvalidStateTransitionError(Exception):
    """Raised when an action attempts an unsupported state change."""
    pass


def validate_transition(current_state: ActionState | str, next_state: ActionState | str) -> bool:
    """Validates whether transitioning from current_state to next_state is legitimate."""
    curr = normalize_state(current_state)
    nxt = normalize_state(next_state)

    valid_next = PERMITTED_TRANSITIONS.get(curr, set())
    if nxt not in valid_next and nxt != curr:
        raise InvalidStateTransitionError(
            f"Invalid lifecycle transition from '{curr.value}' to '{nxt.value}'. "
            f"Allowed next states: {[s.value for s in valid_next]}"
        )
    return True


@dataclass
class StateEvidenceCriteria:
    required_evidence_type: str
    description: str
    can_be_automated: bool


EVIDENCE_RULES: Dict[ActionState, StateEvidenceCriteria] = {
    ActionState.CONFIRMED_EXPOSURE: StateEvidenceCriteria(
        required_evidence_type="USER_OR_SCAN_CONFIRMATION",
        description="User affirms the exposed listing contains their personal telephone number.",
        can_be_automated=True,
    ),
    ActionState.SUBMITTED: StateEvidenceCriteria(
        required_evidence_type="SUBMISSION_RECORD",
        description="Formal opt-out notice dispatched via broker web portal, statutory email, or registered mail.",
        can_be_automated=False,
    ),
    ActionState.ACKNOWLEDGED: StateEvidenceCriteria(
        required_evidence_type="CONFIRMATION_RECEIPT",
        description="Broker issued confirmation ticket ID, email confirmation, or statutory acknowledgment.",
        can_be_automated=False,
    ),
    ActionState.NO_LONGER_VISIBLE_AT_CHECKED_URL: StateEvidenceCriteria(
        required_evidence_type="HTTP_ABSENCE_CHECK",
        description="Affirmative HTTP 404/410 status code OR live 200 with verified absence of phone number.",
        can_be_automated=True,
    ),
    ActionState.SEARCH_RESULT_DELISTED: StateEvidenceCriteria(
        required_evidence_type="SEARCH_INDEX_AUDIT",
        description="Search engine cache / snippet verification confirms listing removed from public search results.",
        can_be_automated=True,
    ),
    ActionState.SOURCE_CONFIRMED_REMOVAL: StateEvidenceCriteria(
        required_evidence_type="STATUTORY_DELETION_RECEIPT",
        description="Data broker issued affirmative confirmation code or signed compliance notice confirming database deletion.",
        can_be_automated=False,
    ),
    ActionState.STILL_VISIBLE: StateEvidenceCriteria(
        required_evidence_type="HTTP_PRESENCE_CHECK",
        description="Live URL rescan detected phone number still present on target webpage.",
        can_be_automated=True,
    ),
    ActionState.INACCESSIBLE_OR_INCONCLUSIVE: StateEvidenceCriteria(
        required_evidence_type="FIREWALL_OR_ERROR_CHECK",
        description="Verification challenged by anti-bot firewall (Cloudflare/DataDome) or server error.",
        can_be_automated=True,
    ),
    ActionState.REAPPEARED: StateEvidenceCriteria(
        required_evidence_type="SUBSEQUENT_SCAN_DETECTION",
        description="Telephone number detected again on a URL previously marked as no longer visible.",
        can_be_automated=True,
    ),
}


def get_state_color_token(state: ActionState | str) -> str:
    """Returns the CSS token/color class corresponding to the truthful lifecycle state."""
    s = normalize_state(state)
    if s == ActionState.SOURCE_CONFIRMED_REMOVAL:
        return "text-emerald-400 bg-emerald-950/40 border-emerald-800"
    elif s in (ActionState.NO_LONGER_VISIBLE_AT_CHECKED_URL, ActionState.SEARCH_RESULT_DELISTED):
        return "text-teal-400 bg-teal-950/40 border-teal-800"
    elif s in (ActionState.SUBMITTED, ActionState.ACKNOWLEDGED, ActionState.AWAITING_VERIFICATION):
        return "text-cyan-400 bg-cyan-950/40 border-cyan-800"
    elif s in (ActionState.AWAITING_USER_APPROVAL, ActionState.CONFIRMED_EXPOSURE, ActionState.REQUEST_PREPARED):
        return "text-amber-400 bg-amber-950/40 border-amber-800"
    elif s in (ActionState.STILL_VISIBLE, ActionState.REAPPEARED):
        return "text-rose-400 bg-rose-950/40 border-rose-800"
    elif s == ActionState.INACCESSIBLE_OR_INCONCLUSIVE:
        return "text-orange-400 bg-orange-950/40 border-orange-800"
    elif s == ActionState.REJECTED:
        return "text-slate-400 bg-slate-900 border-slate-700"
    return "text-blue-400 bg-blue-950/40 border-blue-800"
