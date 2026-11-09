"""Offline regression tests for explicit IMAP consent. Never open a mailbox."""
from acios.flows import imap_reply_guard as guard


def test_default_scan_never_reads_credentials_or_connects(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Mailbox or repository accessed without consent")

    monkeypatch.setattr(guard.imaplib, "IMAP4_SSL", forbidden)
    monkeypatch.setattr(guard, "CareerRepository", forbidden)
    monkeypatch.setattr(guard.os, "getenv", forbidden)
    progress = []
    result = guard.scan_inbox_for_replies_and_bounces(
        progress_callback=lambda value, message: progress.append((value, message))
    )
    assert result["status"] == "DISABLED"
    assert result["bounces_detected"] == 0
    assert result["delivery_notices_needing_review"] == 0
    assert progress[-1][0] == 1.0


def test_flow_default_remains_disabled(monkeypatch):
    monkeypatch.setattr(
        guard.imaplib, "IMAP4_SSL",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("IMAP accessed")),
    )
    assert guard.run_imap_reply_guard()["status"] == "DISABLED"


def test_opt_in_without_credentials_does_not_connect(monkeypatch):
    monkeypatch.delenv("GMAIL_SENDER_EMAIL", raising=False)
    monkeypatch.delenv("GMAIL_USER", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    monkeypatch.setattr(
        guard.imaplib, "IMAP4_SSL",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("IMAP accessed")),
    )
    # The explicit opt-in still requires credentials, and cannot open a mailbox.
    result = guard.scan_inbox_for_replies_and_bounces(allow_live_imap=True)
    assert result["status"] == "DRY_RUN"


def test_opt_in_reaches_existing_connection_path_with_synthetic_fakes(monkeypatch):
    class FakeRepo:
        def __init__(self):
            pass

    calls = []
    def fake_connect(host, port):
        calls.append((host, port))
        raise OSError("synthetic offline failure")

    monkeypatch.setattr(guard, "CareerRepository", FakeRepo)
    monkeypatch.setattr(guard.imaplib, "IMAP4_SSL", fake_connect)
    monkeypatch.setenv("GMAIL_SENDER_EMAIL", "synthetic@example.invalid")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "not-a-real-password")
    result = guard.scan_inbox_for_replies_and_bounces(allow_live_imap=True)
    assert calls == [("imap.gmail.com", 993)]
    assert result["bounces_detected"] == 0
    assert "error" in result
