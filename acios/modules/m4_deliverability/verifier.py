"""
Module 4: Evidence-Based Deliverability & Mailbox Verification Shield.
Performs syntax validation, master suppression checks, DNS MX resolution,
and non-blocking TCP port 25 banner inspection without fabricating mailbox guarantees.
"""

import re
import socket
from typing import List, Optional

import dns.resolver

from acios.core.suppression import SuppressionEngine
from acios.modules.contracts import DeliverabilityStatus, DeliverabilityVerdict


class DeliverabilityShield:
    def __init__(self, suppression_engine: Optional[SuppressionEngine] = None):
        self.supp = suppression_engine or SuppressionEngine()

    def verify_sync(self, email_address: str) -> DeliverabilityVerdict:
        """
        Synchronous verification pipeline:
          1. Syntax Validation (RFC 5322)
          2. Master Suppression Check (past bounces)
          3. DNS MX Resolution
          4. Non-Blocking Socket Probe
        """
        email = (email_address or "").strip().lower()

        # Tier 1: Syntax Validation
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            return DeliverabilityVerdict(
                email=email,
                status=DeliverabilityStatus.INVALID_SYNTAX,
                is_deliverable=False,
                confidence=0.0,
                evidence=["rfc5322_syntax_failed"],
                details="Malformed email syntax failed RFC 5322 check.",
            )

        # Tier 2: Master Suppression Check
        if self.supp.is_suppressed(email):
            return DeliverabilityVerdict(
                email=email,
                status=DeliverabilityStatus.CONFIRMED_BOUNCE,
                is_deliverable=False,
                confidence=1.0,
                evidence=["rfc5322_syntax_ok", "master_suppression_match"],
                details="Email address exists on Master Suppression List from past hard bounce.",
            )

        domain = email.split("@")[-1]
        evidence: List[str] = ["rfc5322_syntax_ok", "not_suppressed"]

        # Tier 3: DNS MX Resolution
        mx_host = None
        try:
            answers = dns.resolver.resolve(domain, "MX", lifetime=3.0)
            sorted_mx = sorted(
                [(r.preference, str(r.exchange).rstrip(".")) for r in answers]
            )
            if sorted_mx:
                mx_host = sorted_mx[0][1]
        except Exception as e:
            return DeliverabilityVerdict(
                email=email,
                status=DeliverabilityStatus.DEAD_DOMAIN,
                is_deliverable=False,
                confidence=0.99,
                mx_host=None,
                evidence=evidence + ["dns_mx_missing"],
                details=f"Domain {domain} has no active MX records ({type(e).__name__}).",
            )

        if not mx_host:
            return DeliverabilityVerdict(
                email=email,
                status=DeliverabilityStatus.DEAD_DOMAIN,
                is_deliverable=False,
                confidence=0.99,
                mx_host=None,
                evidence=evidence + ["dns_mx_empty"],
                details=f"Domain {domain} returned empty MX records.",
            )

        evidence.append(f"dns_mx_resolved:{mx_host}")

        # Tier 4: Non-Blocking Socket Probe (1.0s timeout)
        port_25_open = False
        smtp_code = None
        try:
            sock = socket.create_connection((mx_host, 25), timeout=1.0)
            sock.settimeout(1.0)
            banner = sock.recv(256).decode("utf-8", errors="ignore").strip()
            if banner.startswith("220"):
                smtp_code = 220
            port_25_open = True
            sock.close()
        except Exception:
            port_25_open = False

        is_google = "google" in mx_host.lower() or "aspmx" in mx_host.lower()
        is_m365 = "outlook" in mx_host.lower() or "mail.protection" in mx_host.lower()
        is_catch_all = any(
            p in mx_host.lower() for p in ["zoho", "netease", "sw-tech"]
        )

        if port_25_open:
            evidence.append("tcp_port25_banner_reachable")
            status = (
                DeliverabilityStatus.CATCH_ALL
                if is_catch_all
                else DeliverabilityStatus.MX_BANNER_REACHABLE
            )
            confidence = 0.50 if is_catch_all else 0.65
        else:
            evidence.append("tcp_port25_unreachable")
            status = DeliverabilityStatus.MX_VALID_UNPROBED
            confidence = 0.45

        provider = (
            "Google Workspace"
            if is_google
            else "Microsoft 365"
            if is_m365
            else "Corporate MX"
        )
        return DeliverabilityVerdict(
            email=email,
            status=status,
            is_deliverable=False,
            confidence=confidence,
            mx_host=mx_host,
            is_catch_all=is_catch_all,
            smtp_code=smtp_code,
            evidence=evidence,
            details=(
                f"MX host {mx_host} ({provider}) resolved via DNS. "
                "Individual mailbox existence requires primary source or RCPT confirmation."
            ),
        )
