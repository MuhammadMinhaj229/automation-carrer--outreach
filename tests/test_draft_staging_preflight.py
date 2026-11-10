"""Offline transport preflight regression tests; never connect to Gmail."""
from unittest.mock import patch

from acios.core.draft_engine import DraftEngine
from acios.models.email_draft import EmailDraft


def draft(recipient="review@example.test", subject="Research introduction"):
    # Model construction isolates the transport boundary from unrelated
    # content-length policy; no real candidate or prospect data is used.
    return EmailDraft.model_construct(
        recipient_email=recipient,
        subject_line=subject,
    )


def test_missing_credentials_do_not_open_imap():
    with patch("acios.core.draft_engine.imaplib.IMAP4_SSL") as connect:
        ok, message = DraftEngine(gmail_user="", gmail_app_password="").stage_draft(draft())
    assert not ok
    assert "not configured" in message
    connect.assert_not_called()


def test_newline_in_recipient_rejected_before_network():
    with patch("acios.core.draft_engine.imaplib.IMAP4_SSL") as connect:
        ok, message = DraftEngine(
            gmail_user="sender@example.test", gmail_app_password="synthetic"
        ).stage_draft(draft(recipient="review@example.test\\r\\nBcc: extra@example.test"))
    assert not ok
    assert "Invalid draft header" in message
    connect.assert_not_called()


def test_newline_in_subject_rejected_before_network():
    with patch("acios.core.draft_engine.imaplib.IMAP4_SSL") as connect:
        ok, message = DraftEngine(
            gmail_user="sender@example.test", gmail_app_password="synthetic"
        ).stage_draft(draft(subject="Introduction\\nBcc: extra@example.test"))
    assert not ok
    assert "Invalid draft header" in message
    connect.assert_not_called()


def test_newline_in_sender_rejected_before_network():
    with patch("acios.core.draft_engine.imaplib.IMAP4_SSL") as connect:
        ok, message = DraftEngine(
            gmail_user="sender@example.test\\r\\nBcc: extra@example.test",
            gmail_app_password="synthetic",
        ).stage_draft(draft())
    assert not ok
    assert "Invalid draft header" in message
    connect.assert_not_called()
