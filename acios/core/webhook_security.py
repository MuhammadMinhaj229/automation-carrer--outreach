"""EmailEngine webhook request authentication helpers.

The signature is HMAC-SHA256 over the exact raw HTTP request body, encoded
using URL-safe Base64 without padding, as documented by EmailEngine.
"""

import base64
import hashlib
import hmac


def verify_emailengine_webhook_signature(
    raw_body: bytes,
    signature: str,
    service_secret: str,
) -> bool:
    """Return whether an EmailEngine HMAC signature authenticates raw_body.

    Missing secrets/signatures and malformed inputs fail closed. The caller
    must pass the original request bytes, not parsed/re-serialized JSON.
    """
    if not isinstance(raw_body, bytes) or not service_secret or not signature:
        return False

    try:
        digest = hmac.new(
            service_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).digest()
        expected = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return hmac.compare_digest(expected, signature.strip())
    except (UnicodeEncodeError, TypeError, ValueError):
        return False
