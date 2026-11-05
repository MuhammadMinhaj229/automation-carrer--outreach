"""Offline tests for the opt-in durable suppression registry."""

import sqlite3

import pytest

from acios.core.suppression import SuppressionEngine


def test_persistent_block_survives_new_instances(tmp_path):
    path = tmp_path / "private" / "suppression.sqlite"
    first = SuppressionEngine(suppression_files=[], sqlite_path=path)
    second = SuppressionEngine(suppression_files=[], sqlite_path=path)
    assert not second.is_suppressed("case@example.org")
    first.block(" CASE@Example.org ", reason="hard bounce")
    assert second.is_suppressed("case@example.org")
    assert first.total_blocked == second.total_blocked == 1


def test_idempotent_block_keeps_original_reason_and_timestamp(tmp_path):
    path = tmp_path / "registry.sqlite"
    engine = SuppressionEngine(suppression_files=[], sqlite_path=path)
    engine.block("case@example.org", reason="opt-out")
    with sqlite3.connect(path) as conn:
        before = conn.execute(
            "SELECT reason, created_at FROM suppressed_recipients"
        ).fetchone()
    engine.block("CASE@example.org", reason="later bounce")
    with sqlite3.connect(path) as conn:
        after = conn.execute(
            "SELECT reason, created_at FROM suppressed_recipients"
        ).fetchone()
    assert before == after
    assert after[0] == "opt-out"


def test_bad_recipient_fails_closed_and_cannot_be_blocked(tmp_path):
    engine = SuppressionEngine(suppression_files=[], sqlite_path=tmp_path / "registry.sqlite")
    for address in ("", "no-at-sign", "a@b", "a b@example.org", None):
        assert engine.is_suppressed(address)
        with pytest.raises(ValueError):
            engine.block(address)


def test_unreadable_database_fails_closed(tmp_path):
    path = tmp_path / "registry.sqlite"
    engine = SuppressionEngine(suppression_files=[], sqlite_path=path)
    path.unlink()
    path.mkdir()
    assert engine.is_suppressed("case@example.org")
    with pytest.raises(sqlite3.Error):
        engine.block("case@example.org")


def test_static_suppression_lists_and_legacy_alias(tmp_path):
    static = tmp_path / "suppression.json"
    static.write_text('{"suppressed_emails": [" TEST@EXAMPLE.ORG "]}', encoding="utf-8")
    engine = SuppressionEngine(suppression_files=[static])
    assert engine.is_suppressed("test@example.org")
    engine.add_suppression("other@example.org")
    assert engine.is_suppressed("other@example.org")
