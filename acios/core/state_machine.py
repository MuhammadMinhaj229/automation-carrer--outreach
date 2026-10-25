"""
ACIOS Contact Outreach Lifecycle State Machine.
Enforces rigorous compliance gates and prevents illegal state transitions
(e.g., staging suppressed contacts or dispatching unapproved drafts).
"""

from enum import Enum
from typing import Set, Tuple


class ContactLifecycleState(str, Enum):
    DISCOVERED = "DISCOVERED"
    RESEARCHED = "RESEARCHED"
    CONTACT_VERIFIED = "CONTACT_VERIFIED"
    DRAFT_STAGED = "DRAFT_STAGED"
    APPROVED = "APPROVED"
    DISPATCHED = "DISPATCHED"
    REPLIED = "REPLIED"
    BOUNCED = "BOUNCED"
    CLOSED = "CLOSED"


# Legal directed transitions
VALID_TRANSITIONS: Set[Tuple[ContactLifecycleState, ContactLifecycleState]] = {
    (ContactLifecycleState.DISCOVERED, ContactLifecycleState.RESEARCHED),
    (ContactLifecycleState.RESEARCHED, ContactLifecycleState.CONTACT_VERIFIED),
    (ContactLifecycleState.CONTACT_VERIFIED, ContactLifecycleState.DRAFT_STAGED),
    (ContactLifecycleState.DRAFT_STAGED, ContactLifecycleState.APPROVED),
    (ContactLifecycleState.APPROVED, ContactLifecycleState.DISPATCHED),
    # Replies and bounces can occur post-dispatch (or post-staging if historical)
    (ContactLifecycleState.DISPATCHED, ContactLifecycleState.REPLIED),
    (ContactLifecycleState.DISPATCHED, ContactLifecycleState.BOUNCED),
    (ContactLifecycleState.DRAFT_STAGED, ContactLifecycleState.REPLIED),
    (ContactLifecycleState.DRAFT_STAGED, ContactLifecycleState.BOUNCED),
    (ContactLifecycleState.REPLIED, ContactLifecycleState.CLOSED),
    (ContactLifecycleState.BOUNCED, ContactLifecycleState.CLOSED),
    # Human skip or close at any early stage
    (ContactLifecycleState.DISCOVERED, ContactLifecycleState.CLOSED),
    (ContactLifecycleState.RESEARCHED, ContactLifecycleState.CLOSED),
    (ContactLifecycleState.CONTACT_VERIFIED, ContactLifecycleState.CLOSED),
    (ContactLifecycleState.DRAFT_STAGED, ContactLifecycleState.CLOSED),
}


class StateTransitionError(Exception):
    """Raised when an outreach lifecycle transition violates system safety policies."""
    pass


class OutreachStateMachine:
    """Validates and applies lifecycle status transitions."""

    @staticmethod
    def can_transition(
        current_state: ContactLifecycleState, 
        target_state: ContactLifecycleState
    ) -> bool:
        return (current_state, target_state) in VALID_TRANSITIONS

    @staticmethod
    def transition(
        current_state: ContactLifecycleState,
        target_state: ContactLifecycleState,
        is_suppressed: bool = False,
        verification_status: str = "Unverified",
        word_count: int = 0
    ) -> ContactLifecycleState:
        """Applies validation guardrails before transitioning state."""
        if not OutreachStateMachine.can_transition(current_state, target_state):
            raise StateTransitionError(
                f"Illegal lifecycle transition: Cannot move from {current_state.value} to {target_state.value}."
            )

        # Safety Gate 1: Suppression Check
        if is_suppressed and target_state in [ContactLifecycleState.DRAFT_STAGED, ContactLifecycleState.APPROVED, ContactLifecycleState.DISPATCHED]:
            raise StateTransitionError("Safety Gate Violation: Contact is SUPPRESSED. Outreach actions are forbidden.")

        # Safety Gate 2: Verification Check for Staging
        if target_state == ContactLifecycleState.DRAFT_STAGED:
            if "Unverified" in verification_status or "Bounced" in verification_status:
                raise StateTransitionError("Verification Gate Violation: Cannot stage draft for unverified address.")
            if word_count < 100 or word_count > 160:
                raise StateTransitionError(f"Word Count Gate Violation: Draft has {word_count} words (must be 100-160).")

        return target_state
