"""Offline regression tests for the EmailEngine bounce adapter and native events."""

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


def test_native_message_new_is_not_assumed_to_be_an_outreach_reply():
    repo = FakeRepository()
    supp = SuppressionEngine(suppression_files=[])
    gateway = EmailEngineGateway(repo=repo, supp=supp)

    result = gateway.process_webhook_event({
        "event": "messageNew",
        "account": "synthetic-account",
        "data": {
            "from": {"address": "person@example.org"},
            "subject": "Synthetic unrelated inbound message",
            "messageId": "synthetic-message-id",
            "isBounce": True,
        },
    })

    assert result["status"] == "REVIEW_REQUIRED"
    assert result["action"] == "REVIEW_INBOUND_MESSAGE"
    assert result["sender"] == "person@example.org"
    assert repo.statuses == []
    assert repo.events == []
    assert not supp.is_suppressed("person@example.org")


def test_native_message_bounce_is_review_only_and_never_auto_suppresses():
    repo = FakeRepository()
    supp = SuppressionEngine(suppression_files=[])
    gateway = EmailEngineGateway(repo=repo, supp=supp)

    result = gateway.process_webhook_event({
        "event": "messageBounce",
        "account": "synthetic-account",
        "data": {
            "recipient": " Bounced@Example.org ",
            "action": "failed",
            "messageId": "<synthetic-original@example.org>",
            "bounceMessage": "synthetic-bounce-id",
            "response": {
                "status": "5.1.1",
                "category": "user_unknown",
                "recommendedAction": "remove",
            },
        },
    })

    assert result["status"] == "REVIEW_REQUIRED"
    assert result["action"] == "REVIEW_BOUNCE"
    assert result["recipient"] == "bounced@example.org"
    assert result["response_status"] == "5.1.1"
    assert result["recommended_action"] == "remove"
    assert repo.statuses == []
    assert repo.events == []
    assert not supp.is_suppressed("bounced@example.org")


def test_native_delivery_errors_and_terminal_failures_are_review_only():
    for event_type in ("messageDeliveryError", "messageFailed"):
        repo = FakeRepository()
        supp = SuppressionEngine(suppression_files=[])
        gateway = EmailEngineGateway(repo=repo, supp=supp)

        result = gateway.process_webhook_event({
            "event": event_type,
            "data": {
                "queueId": "synthetic-queue-id",
                "messageId": "<synthetic-message@example.org>",
                "errorCode": "synthetic-error",
            },
        })

        assert result["status"] == "REVIEW_REQUIRED"
        assert result["action"] == "REVIEW_DELIVERY_FAILURE"
        assert result["queue_id"] == "synthetic-queue-id"
        assert repo.statuses == []
        assert repo.events == []
        assert supp.total_blocked == 0


def test_native_complaint_is_review_only():
    repo = FakeRepository()
    supp = SuppressionEngine(suppression_files=[])
    gateway = EmailEngineGateway(repo=repo, supp=supp)

    result = gateway.process_webhook_event({
        "event": "messageComplaint",
        "data": {"messageId": "<synthetic-message@example.org>"},
    })

    assert result["status"] == "REVIEW_REQUIRED"
    assert result["action"] == "REVIEW_COMPLAINT"
    assert repo.statuses == []
    assert repo.events == []
    assert supp.total_blocked == 0


def test_native_message_sent_is_recognized_as_provider_acceptance():
    repo = FakeRepository()
    gateway = EmailEngineGateway(repo=repo, supp=SuppressionEngine(suppression_files=[]))

    result = gateway.process_webhook_event({
        "event": "messageSent",
        "data": {"messageId": "<synthetic-message@example.org>"},
    })

    assert result["status"] == "PROCESSED"
    assert result["action"] == "LOG_DELIVERY"
    assert "final inbox delivery is not implied" in result["message"]
    assert repo.statuses == []
    assert repo.events == []
