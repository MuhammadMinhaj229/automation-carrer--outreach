"""Synthetic offline tests for MIME attachment filename preflight."""
from unittest.mock import patch

import pytest

from acios.core.draft_engine import DraftEngine
from acios.models.email_draft import EmailDraft


@pytest.mark.parametrize("filename", [
    "resume.pdf\\r\\nBcc: other@example.test",
    "resume.pdf\\nX-Test: injected",
    "resume.pdf\\rX-Test: injected",
])
def test_unsafe_attachment_filename_never_connects(filename):
    draft = EmailDraft.model_construct(
        recipient_email="review@example.test", subject_line="Research introduction"
    )
    engine = DraftEngine(
        gmail_user="sender@example.test", gmail_app_password="synthetic"
    )
    with patch("acios.core.draft_engine.imaplib.IMAP4_SSL") as connect:
        ok, message = engine.stage_draft(
            draft, attachment_bytes=b"%PDF-1.4 synthetic", attachment_filename=filename
        )
    assert not ok
    assert "Invalid attachment filename" in message
    connect.assert_not_called()


def test_literal_backslash_sequences_are_not_control_characters():
    draft = EmailDraft.model_construct(
        recipient_email="review@example.test", subject_line="Research introduction"
    )
    engine = DraftEngine(
        gmail_user="sender@example.test", gmail_app_password="synthetic"
    )
    with patch("acios.core.draft_engine.imaplib.IMAP4_SSL") as connect:
        connect.side_effect = OSError("synthetic network guard")
        ok, message = engine.stage_draft(
            draft, attachment_filename=r"resume\\nnotes.pdf"
        )
    assert not ok
    assert "Invalid attachment filename" not in message
    connect.assert_called_once()
