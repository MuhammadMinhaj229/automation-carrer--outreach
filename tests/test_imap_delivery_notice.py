"""Offline IMAP delivery-notice classification tests; no mailbox access."""
from acios.flows import imap_reply_guard as guard
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



def test_scan_never_fetches_delivery_notice_body_or_writes_suppression(monkeypatch):
    from contextlib import nullcontext

    class FakeCursor:
        def execute(self, *args, **kwargs):
            raise AssertionError("A suspected delivery notice must not mutate contact/suppression rows")

    class FakeConnection:
        def __init__(self):
            self.committed = False

        def cursor(self):
            return FakeCursor()

        def commit(self):
            self.committed = True

    connection = FakeConnection()

    class FakeRepository:
        def list_contacts(self):
            return []

        def _conn(self):
            return nullcontext(connection)

    class FakeMail:
        def __init__(self):
            self.fetch_queries = []

        def login(self, *args):
            return "OK", []

        def select(self, *args, **kwargs):
            return "OK", []

        def search(self, *args):
            return "OK", [b"1"]

        def fetch(self, message_id, query):
            self.fetch_queries.append(query)
            if "HEADER.FIELDS" in query:
                headers = (
                    b"From: Mail Delivery <mailer-daemon@example.org>\r\n"
                    b"Subject: Undeliverable: synthetic message\r\n"
                )
                return "OK", [(message_id, headers)]
            raise AssertionError("Delivery-notice body fetch is prohibited")

        def close(self):
            return "OK", []

        def logout(self):
            return "BYE", []

    fake_mail = FakeMail()
    monkeypatch.setattr(guard, "CareerRepository", FakeRepository)
    monkeypatch.setattr(guard.imaplib, "IMAP4_SSL", lambda host, port: fake_mail)
    monkeypatch.setenv("GMAIL_SENDER_EMAIL", "sender@example.invalid")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "synthetic-not-a-secret")

    result = guard.scan_inbox_for_replies_and_bounces(allow_live_imap=True)

    assert result["status"] == "SUCCESS"
    assert result["bounces_detected"] == 0
    assert result["delivery_notices_needing_review"] == 1
    assert len(fake_mail.fetch_queries) == 1
    assert "HEADER.FIELDS" in fake_mail.fetch_queries[0]
    assert connection.committed
