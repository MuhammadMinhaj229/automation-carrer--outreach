"""Offline regression tests for the legacy EmailEngine bounce adapter."""
from acios.core.emailengine_gateway import EmailEngineGateway
from acios.core.suppression import SuppressionEngine


class FakeRepository:
    def __init__(self):
        self.statuses = []
        self.events = []

    def update_contact_status(self, email, status):
        self.statuses.append((email, status))
        return True

    def record_outreach_event(self, **kwargs):
        self.events.append(kwargs)


def test_explicit_hard_bounce_blocks_recipient_without_missing_method():
    repo = FakeRepository()
    supp = SuppressionEngine(suppression_files=[])
    gateway = EmailEngineGateway(repo=repo, supp=supp)
    result = gateway.process_webhook_event({
        "event": "bounce",
        "data": {"recipient": "  Test@Example.org ", "bounce_type": "hard"},
    })
    assert result["action"] == "SUPPRESS_RECIPIENT"
    assert supp.is_suppressed("test@example.org")
    assert repo.statuses == [("test@example.org", "BOUNCED")]
    assert len(repo.events) == 1
    assert repo.events[0]["action_type"] == "BOUNCE_DETECTED"


def test_soft_and_unknown_bounces_are_not_misclassified_as_permanent():
    for bounce_type in ("soft", None):
        repo = FakeRepository()
        supp = SuppressionEngine(suppression_files=[])
        gateway = EmailEngineGateway(repo=repo, supp=supp)
        result = gateway.process_webhook_event({
            "event": "bounce",
            "data": {"recipient": "soft@example.org", "bounce_type": bounce_type},
        })
        assert result["action"] == "REVIEW_BOUNCE"
        assert not supp.is_suppressed("soft@example.org")
        assert repo.statuses == []
        assert repo.events == []


def test_missing_recipient_and_malformed_payload_fail_closed():
    repo = FakeRepository()
    supp = SuppressionEngine(suppression_files=[])
    gateway = EmailEngineGateway(repo=repo, supp=supp)
    assert gateway.process_webhook_event({
        "event": "bounce", "data": {"bounce_type": "hard"}
    })["action"] == "REVIEW_BOUNCE"
    assert gateway.process_webhook_event({
        "event": "bounce", "data": "not a mapping"
    })["status"] == "IGNORED"
    assert not repo.statuses
    assert not repo.events
