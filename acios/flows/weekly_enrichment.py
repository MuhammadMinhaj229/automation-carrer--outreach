"""
ACIOS Workflow: Weekly Organization & Decision-Maker Enrichment.
Orchestrated with Prefect to enrich organizations missing verified technical contacts,
avoid speculative contact creation until a source-backed discovery adapter exists.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime, timezone

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
    """Inserts verified candidates into the contacts table."""
    repo = CareerRepository()
    now_iso = datetime.now(timezone.utc).isoformat()
    inserted = 0
    with repo._conn() as conn:
        cursor = conn.cursor()
        for lead in leads:
            cursor.execute("""
                INSERT INTO contacts (
                    organization_name, name, role, work_email,
                    verification_status, outreach_status, notes, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'Untouched', ?, ?)
                ON CONFLICT(organization_name, name) DO UPDATE SET
                    work_email = excluded.work_email,
                    verification_status = excluded.verification_status,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
            """, (
                lead["organization_name"],
                lead["name"],
                lead["role"],
                lead["work_email"],
                lead["verification_status"],
                lead["notes"],
                now_iso
            ))
            inserted += 1
        conn.commit()
    return inserted


@flow(name="weekly_enrichment_flow")
def run_weekly_enrichment(batch_size: int = 5):
    """Legacy workflow; returns zero until evidence-backed contacts are supplied."""
    orgs = identify_target_organizations(limit=batch_size)
    if not orgs:
        print("[*] All cataloged organizations have active contacts.")
        return 0

    leads = generate_and_verify_candidates(orgs)
    count = persist_enriched_contacts(leads)
    if count > 0:
        export_all()
    print(f"[*] Weekly enrichment flow completed. Successfully enriched {count} decision-makers.")
    return count


if __name__ == "__main__":
    run_weekly_enrichment()
