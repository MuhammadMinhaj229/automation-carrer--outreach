"""Offline regression tests for EmailEngine webhook HMAC authentication."""

import base64
import hashlib
import hmac

from acios.core.webhook_security import verify_emailengine_webhook_signature


TEST_SECRET = "synthetic-test-only-secret"
RAW_BODY = b'{"event":"messageNew","data":{"subject":"Synthetic"}}'


def _signature(body: bytes, secret: str = TEST_SECRET) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def test_accepts_signature_for_exact_raw_body():
    assert verify_emailengine_webhook_signature(
        RAW_BODY, _signature(RAW_BODY), TEST_SECRET
    )


def test_rejects_modified_body_and_signature():
    assert not verify_emailengine_webhook_signature(
        RAW_BODY + b" ", _signature(RAW_BODY), TEST_SECRET
    )
    assert not verify_emailengine_webhook_signature(
        RAW_BODY, _signature(RAW_BODY)[:-1] + "A", TEST_SECRET
    )


def test_missing_secret_or_signature_fails_closed():
    assert not verify_emailengine_webhook_signature(RAW_BODY, _signature(RAW_BODY), "")
    assert not verify_emailengine_webhook_signature(RAW_BODY, "", TEST_SECRET)
    assert not verify_emailengine_webhook_signature(RAW_BODY, "", "")


def test_non_ascii_signature_is_rejected_without_exception():
    assert not verify_emailengine_webhook_signature(RAW_BODY, "☃", TEST_SECRET)
