"""
ACIOS Stage 3: Hunter.io Email Verifier Client.
Integrates Hunter.io REST API (v2) for deep SMTP-level mailbox verification,
accept-all detection, and score benchmarking.
"""

import os
import requests
from typing import Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

from acios.core.interfaces import VerifierProvider, VerificationResult
from acios.models.contact import VerificationStatus

# Load environment variables if present
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(BASE_DIR / ".env")


class HunterVerifier(VerifierProvider):
    """Stage 3: Hunter.io API Verifier Client."""

    BASE_URL = "https://api.hunter.io/v2/email-verifier"

    def __init__(self, api_key: Optional[str] = None, timeout: float = 8.0):
        self.api_key = api_key or os.getenv("HUNTER_API_KEY")
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def verify(self, email: str) -> VerificationResult:
        clean_email = (email or "").strip().lower()
        if not self.is_configured:
            return VerificationResult(
                email=clean_email,
                status=VerificationStatus.PATTERN_PREDICTED,
                confidence_score=0.5,
                provider="HunterVerifier",
                details="Hunter.io API key not configured in environment (.env); skipped API verification"
            )

        try:
            params = {
                "email": clean_email,
                "api_key": self.api_key
            }
            resp = requests.get(self.BASE_URL, params=params, timeout=self.timeout)
            
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                status_str = data.get("status", "unknown")
                result_str = data.get("result", "unknown")
                score = data.get("score", 50) / 100.0
                mx_valid = data.get("mx_records", True)
                is_disp = data.get("disposable", False)
                smtp_check = data.get("smtp_check", False)

                if status_str == "valid" or result_str == "deliverable":
                    v_status = VerificationStatus.VERIFIED_PRIMARY
                elif status_str in ["accept_all", "webmail"]:
                    v_status = VerificationStatus.PATTERN_PREDICTED
                elif status_str == "invalid" or result_str == "undeliverable":
                    v_status = VerificationStatus.UNVERIFIED
                else:
                    v_status = VerificationStatus.PATTERN_PREDICTED

                details = f"Hunter status={status_str}, result={result_str}, score={int(score*100)}%, smtp_check={smtp_check}"
                return VerificationResult(
                    email=clean_email,
                    status=v_status,
                    confidence_score=score,
                    mx_valid=mx_valid,
                    is_disposable=is_disp,
                    provider="HunterVerifier",
                    details=details
                )
            elif resp.status_code == 401:
                return VerificationResult(
                    email=clean_email,
                    status=VerificationStatus.PATTERN_PREDICTED,
                    confidence_score=0.5,
                    provider="HunterVerifier",
                    details="Hunter.io authentication failed: Invalid API key"
                )
            elif resp.status_code == 429:
                return VerificationResult(
                    email=clean_email,
                    status=VerificationStatus.PATTERN_PREDICTED,
                    confidence_score=0.5,
                    provider="HunterVerifier",
                    details="Hunter.io rate limit / monthly quota exceeded"
                )
            else:
                return VerificationResult(
                    email=clean_email,
                    status=VerificationStatus.PATTERN_PREDICTED,
                    confidence_score=0.5,
                    provider="HunterVerifier",
                    details=f"Hunter.io API returned HTTP {resp.status_code}: {resp.text[:100]}"
                )

        except requests.exceptions.Timeout:
            return VerificationResult(
                email=clean_email,
                status=VerificationStatus.PATTERN_PREDICTED,
                confidence_score=0.5,
                provider="HunterVerifier",
                details="Hunter.io API request timed out"
            )
        except Exception as e:
            return VerificationResult(
                email=clean_email,
                status=VerificationStatus.PATTERN_PREDICTED,
                confidence_score=0.5,
                provider="HunterVerifier",
                details=f"Hunter.io verification error: {str(e)}"
            )
