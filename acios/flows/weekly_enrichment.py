"""
ACIOS Workflow: Weekly Organization & Decision-Maker Enrichment.
Orchestrated with Prefect to enrich organizations missing verified technical contacts,
avoid speculative contact creation until a source-backed discovery adapter exists.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    from prefect import flow, task
    PREFECT_ENABLED = True
except ImportError:
    def task(name=None, **kwargs):
        def decorator(fn):
            return fn
        return decorator
    def flow(name=None, **kwargs):
        def decorator(fn):
            return fn
        return decorator
    PREFECT_ENABLED = False

from acios.core.repository import CareerRepository
from acios.reports.export import export_all


@task(name="identify_organizations_needing_enrichment")
def identify_target_organizations(limit: int = 10) -> List[Dict[str, Any]]:
    """Identifies companies with no verified contacts or untouched outreach."""
    repo = CareerRepository()
    with repo._conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT o.name, o.country, o.sector, o.website
            FROM organizations o
            WHERE (SELECT COUNT(*) FROM contacts WHERE organization_name = o.name) = 0
               OR (SELECT COUNT(*) FROM contacts WHERE organization_name = o.name AND verification_status = 'Unverified') > 0
            LIMIT ?
        """, (limit,))
        rows = [dict(r) for r in cursor.fetchall()]
    print(f"[*] Found {len(rows)} organizations requiring contact enrichment.")
    return rows


@task(name="generate_and_verify_candidates")
def generate_and_verify_candidates(orgs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Fail closed until a source-backed contact discovery adapter exists.

    Organization names, website domains, email permutations and deliverability
    scores do not establish a person's identity, job title or email ownership.
    This legacy workflow must not invent decision-makers or persist guesses.
    """
    _ = orgs
    return []


@task(name="persist_enriched_contacts")
def persist_enriched_contacts(leads: List[Dict[str, Any]]) -> int:
    """Fail closed until a provenance/approval ledger validates every contact.

    The legacy caller-supplied verification_status is not evidence. A source URL
    or an MX check alone cannot establish identity or mailbox ownership.
    """
    if not leads:
        return 0
    raise RuntimeError(
        "Legacy contact persistence is disabled: source-backed identity, "
        "email ownership, and explicit human approval are not validated."
    )


@flow(name="weekly_enrichment_flow")
def run_weekly_enrichment(batch_size: int = 5):
    """Legacy workflow; returns zero until evidence-backed contacts are supplied."""
    orgs = identify_target_organizations(limit=batch_size)
    if not orgs:
        print("[*] All cataloged organizations have active contacts.")
        return 0

    leads = generate_and_verify_candidates(orgs)
    # No evidence-backed leads means no database write or report export.
    # This is important even when persistence has side effects for empty input.
    if not leads:
        print("[*] No source-backed contacts to persist; skipping writes and exports.")
        return 0

    count = persist_enriched_contacts(leads)
    if count > 0:
        export_all()
    print(f"[*] Weekly enrichment flow completed. Successfully enriched {count} decision-makers.")
    return count


if __name__ == "__main__":
    run_weekly_enrichment()
