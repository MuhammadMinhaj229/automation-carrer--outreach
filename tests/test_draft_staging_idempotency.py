"""Offline regressions for idempotent Gmail draft staging."""

from email import policy
from email.parser import BytesParser

import pytest

from acios.core.draft_engine import DraftEngine, build_staging_marker
from acios.models.email_draft import EmailDraft


PDF_A = b"%PDF-1.7\\nsynthetic resume bytes"
PDF_B = b"%PDF-1.7\\ndifferent synthetic resume bytes"


def make_draft(subject="A question about research workflows"):
    return EmailDraft(
        recipient_name="Synthetic Recipient",
        recipient_email="recipient@example.invalid",
        recipient_role="Research Lead",
        organization_name="Synthetic Organization",
        subject_line=subject,
        paragraphs=[" ".join(["research"] * 100)],
    )


class FakeIMAP:
    def __init__(self, *, select_status="OK", search_status="OK", search_result=b""):
        self.select_status = select_status
        self.search_status = search_status
        self.search_result = search_result
        self.selected = []
        self.searches = []
        self.appends = []
        self.logged_out = False

    def login(self, username, password):
        return "OK", [b"authenticated"]

    def select(self, mailbox, readonly=False):
        self.selected.append((mailbox, readonly))
        return self.select_status, [b"1"]

    def search(self, charset, *criteria):
        self.searches.append((charset, *criteria))
        return self.search_status, [self.search_result]

    def append(self, mailbox, flags, date_time, message):
        self.appends.append((mailbox, flags, date_time, message))
        return "OK", [b"APPEND completed"]

    def logout(self):
        self.logged_out = True
        return "BYE", [b"logged out"]


def install_fake_imap(monkeypatch, fake):
    monkeypatch.setattr(
        "acios.core.draft_engine.imaplib.IMAP4_SSL",
        lambda host: fake,
    )


def test_staging_marker_is_stable_but_tracks_content_and_attachment_versions():
    draft = make_draft()
    marker = build_staging_marker(
        draft, draft_id=17, attachment_bytes=PDF_A, attachment_filename="resume.pdf"
    )
    assert marker == build_staging_marker(
        draft, draft_id=17, attachment_bytes=PDF_A, attachment_filename="resume.pdf"
    )
    assert marker != build_staging_marker(
        draft.model_copy(update={"subject_line": "A different question"}),
        draft_id=17,
        attachment_bytes=PDF_A,
        attachment_filename="resume.pdf",
    )
    assert marker != build_staging_marker(
        draft, draft_id=17, attachment_bytes=PDF_B, attachment_filename="resume.pdf"
    )
    assert marker != build_staging_marker(
        draft, draft_id=18, attachment_bytes=PDF_A, attachment_filename="resume.pdf"
    )


def test_stage_draft_appends_only_after_successful_empty_search(monkeypatch):
    fake = FakeIMAP(search_result=b"")
    install_fake_imap(monkeypatch, fake)
    draft = make_draft()
    engine = DraftEngine(gmail_user="synthetic@example.invalid", gmail_app_password="not-a-secret")

    ok, detail = engine.stage_draft(
        draft,
        attachment_bytes=PDF_A,
        attachment_filename="resume.pdf",
        draft_id=17,
    )

    assert ok is True
    assert "Successfully staged" in detail
    assert fake.selected == [('"[Gmail]/Drafts"', False)]
    assert fake.searches == [
        (None, "HEADER", "X-ACIOS-Draft-ID", build_staging_marker(
            draft, draft_id=17, attachment_bytes=PDF_A, attachment_filename="resume.pdf"
        ))
    ]
    assert len(fake.appends) == 1
    parsed = BytesParser(policy=policy.default).parsebytes(fake.appends[0][3])
    assert parsed["X-ACIOS-Draft-ID"] == fake.searches[0][-1]
    assert fake.logged_out is True


def test_stage_draft_returns_existing_match_without_appending(monkeypatch):
    fake = FakeIMAP(search_result=b"4 9")
    install_fake_imap(monkeypatch, fake)
    engine = DraftEngine(gmail_user="synthetic@example.invalid", gmail_app_password="not-a-secret")

    ok, detail = engine.stage_draft(
        make_draft(),
        attachment_bytes=PDF_A,
        attachment_filename="resume.pdf",
        draft_id=17,
    )

    assert ok is True
    assert "already staged" in detail
    assert fake.appends == []
    assert fake.logged_out is True


@pytest.mark.parametrize(
    ("select_status", "search_status", "search_result"),
    [
        ("NO", "OK", b""),
        ("OK", "NO", b""),
    ],
)
def test_stage_draft_fails_closed_when_mailbox_or_search_is_unavailable(
    monkeypatch, select_status, search_status, search_result
):
    fake = FakeIMAP(
        select_status=select_status,
        search_status=search_status,
        search_result=search_result,
    )
    install_fake_imap(monkeypatch, fake)
    engine = DraftEngine(gmail_user="synthetic@example.invalid", gmail_app_password="not-a-secret")

    ok, detail = engine.stage_draft(
        make_draft(),
        attachment_bytes=PDF_A,
        attachment_filename="resume.pdf",
        draft_id=17,
    )

    assert ok is False
    assert "not attempted" in detail or "failed closed" in detail
    assert fake.appends == []
    assert fake.logged_out is True


def test_stage_draft_without_persisted_id_uses_content_snapshot(monkeypatch):
    fake = FakeIMAP(search_result=b"")
    install_fake_imap(monkeypatch, fake)
    engine = DraftEngine(gmail_user="synthetic@example.invalid", gmail_app_password="not-a-secret")
    draft = make_draft()

    ok, _ = engine.stage_draft(
        draft, attachment_bytes=PDF_A, attachment_filename="resume.pdf"
    )

    assert ok is True
    expected = build_staging_marker(
        draft, attachment_bytes=PDF_A, attachment_filename="resume.pdf"
    )
    assert fake.searches[0][-1] == expected


def test_stage_draft_does_not_connect_without_credentials(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("IMAP must not be opened without credentials")

    monkeypatch.setattr("acios.core.draft_engine.imaplib.IMAP4_SSL", forbidden)
    engine = DraftEngine(gmail_user="", gmail_app_password="")

    ok, detail = engine.stage_draft(make_draft(), attachment_bytes=PDF_A)

    assert ok is False
    assert "not configured" in detail
