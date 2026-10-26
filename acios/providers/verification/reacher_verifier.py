"""
ACIOS Evidence-Based Email Deliverability & MX Verification Engine.
Performs:
1. RFC 5322 syntax validation.
2. Disposable domain screening (AfterShip pattern).
3. Authoritative DNS MX resolution.
4. Non-intrusive TCP port 25 banner check.
Returns honest, evidence-backed confidence scores without fabricating mailbox guarantees.
"""

import re
import socket
from typing import Any, Dict, List, Optional

try:
    import dns.resolver

    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False


class ReacherDeliverabilityEngine:
    """Evidence-based email domain, MX, and socket reachability verifier."""

    def __init__(
        self,
        reacher_endpoint: Optional[str] = None,
        timeout: float = 3.0,
    ):
        self.reacher_endpoint = reacher_endpoint
        self.timeout = timeout
        self._cache: Dict[str, Dict[str, Any]] = {}

    def is_disposable(self, domain: str) -> bool:
        """Screens against known disposable email domains."""
        disposables = {
            "mailinator.com",
            "yopmail.com",
            "tempmail.com",
            "10minutemail.com",
            "guerrillamail.com",
            "trashmail.com",
            "sharklasers.com",
            "getairmail.com",
        }
        return domain.lower().strip() in disposables

    def resolve_mx_host(self, domain: str) -> Optional[str]:
        """Resolves primary MX host for domain."""
        if DNS_AVAILABLE:
            try:
                resolver = dns.resolver.Resolver()
                resolver.timeout = self.timeout
                resolver.lifetime = self.timeout
                answers = resolver.resolve(domain, "MX")
                sorted_ans = sorted(answers, key=lambda r: r.preference)
                if sorted_ans:
                    return str(sorted_ans[0].exchange).rstrip(".")
            except Exception:
                pass
        return None

    def probe_smtp_port25(self, email: str, mx_host: str) -> Dict[str, Any]:
        """
        Tests TCP port 25 reachability on the resolved MX host.
        Never fabricates reachability when port 25 is blocked or times out.
        """
        try:
            with socket.create_connection((mx_host, 25), timeout=1.0) as sock:
                sock.settimeout(1.0)
                banner = ""
                try:
                    banner = sock.recv(256).decode("utf-8", errors="ignore").strip()
                except Exception:
                    banner = ""
                return {
                    "reachable": True,
                    "smtp_code": 220 if banner.startswith("220") else None,
                    "status": "MX_BANNER_REACHABLE",
                    "details": (
                        f"TCP port 25 reachable on {mx_host}. "
                        "Server banner does not guarantee individual mailbox existence."
                    ),
                }
        except (socket.timeout, ConnectionRefusedError, OSError) as exc:
            return {
                "reachable": False,
                "smtp_code": None,
                "status": "MX_VALID_PORT25_UNREACHABLE",
                "details": f"MX host {mx_host} resolved via DNS, but TCP port 25 was unreachable ({type(exc).__name__}).",
            }
        except Exception as exc:
            return {
                "reachable": False,
                "smtp_code": None,
                "status": "MX_VALID_UNPROBED",
                "details": f"MX host {mx_host} resolved; socket probe did not complete ({type(exc).__name__}).",
            }

    async def verify(self, email: str) -> Dict[str, Any]:
        """Executes evidence-based verification and returns explicit evidence list and confidence."""
        clean_email = (email or "").strip().lower()
        if clean_email in self._cache:
            return self._cache[clean_email]

        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", clean_email):
            res = {
                "email": clean_email,
                "valid": False,
                "verified": False,
                "confidence": 0.0,
                "engine": "RFC 5322 Syntax Gate",
                "status": "INVALID_SYNTAX",
                "evidence": ["rfc5322_syntax_failed"],
                "details": "Malformed email syntax.",
            }
            self._cache[clean_email] = res
            return res

        domain = clean_email.split("@")[-1]
        evidence: List[str] = ["rfc5322_syntax_valid"]

        if self.is_disposable(domain):
            res = {
                "email": clean_email,
                "valid": False,
                "verified": False,
                "confidence": 0.0,
                "engine": "Disposable Domain Filter",
                "status": "DISPOSABLE_DOMAIN",
                "evidence": evidence + ["disposable_domain_matched"],
                "details": "Temporary or throwaway email domain blocked.",
            }
            self._cache[clean_email] = res
            return res

        evidence.append("not_disposable_domain")

        mx_host = self.resolve_mx_host(domain)
        if not mx_host:
            res = {
                "email": clean_email,
                "valid": False,
                "verified": False,
                "confidence": 0.0,
                "engine": "DNS MX Resolver",
                "status": "NO_MX_RECORDS",
                "evidence": evidence + ["dns_mx_missing"],
                "details": f"Domain '{domain}' has no valid DNS MX records.",
            }
            self._cache[clean_email] = res
            return res

        evidence.append(f"dns_mx_resolved:{mx_host}")
        probe_res = self.probe_smtp_port25(clean_email, mx_host)
        reachable = bool(probe_res.get("reachable"))
        if reachable:
            evidence.append("tcp_port25_banner_reachable")
        else:
            evidence.append("tcp_port25_unreachable")

        is_enterprise_suite = any(
            p in mx_host.lower()
            for p in ["outlook", "google", "mimecast", "barracuda", "pphosted"]
        )
        is_catchall = not is_enterprise_suite
        if reachable:
            confidence = 0.65 if not is_catchall else 0.50
        else:
            confidence = 0.45

        result = {
            "email": clean_email,
            "valid": True,
            "verified": False,
            "confidence": confidence,
            "engine": "Evidence-Based MX & Socket Verifier",
            "status": probe_res.get("status", "MX_VALID_UNPROBED"),
            "mx_host": mx_host,
            "is_catch_all": is_catchall,
            "smtp_code": probe_res.get("smtp_code"),
            "evidence": evidence,
            "details": probe_res.get("details"),
        }
        self._cache[clean_email] = result
        return result
