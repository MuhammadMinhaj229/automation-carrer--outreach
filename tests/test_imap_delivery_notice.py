"""Offline IMAP delivery-notice classification tests; no mailbox access."""
from acios.flows.imap_reply_guard import suspected_delivery_failure


def test_mailer_daemon_notice_requires_review():
    assert suspected_delivery_failure("Mail Delivery <mailer-daemon@example.org>", "Delivery status notification")


def test_postmaster_notice_requires_review():
    assert suspected_delivery_failure("postmaster@example.org", "Message delayed")


def test_generic_failure_word_is_not_a_bounce_verdict():
    assert not suspected_delivery_failure("colleague@example.org", "Failure modes in our research")


def test_unrelated_reply_is_not_delivery_notice():
    assert not suspected_delivery_failure("person@example.org", "Re: meeting notes")


def test_explicit_undeliverable_subject_requires_review():
    assert suspected_delivery_failure("system@example.org", "Undeliverable: message")
