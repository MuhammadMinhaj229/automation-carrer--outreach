"""
ACIOS Workflow: Weekly Organization & Decision-Maker Enrichment.
Orchestrated with Prefect to enrich organizations missing verified technical contacts,
generate standard RFC email permutations, and pass them through the verification waterfall.
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
from acios.core.permutator import EmailPermutator
from acios.providers.verification.waterfall import EmailVerificationWaterfall
from acios.models.contact import Contact, VerificationStatus, OutreachStatus
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
    """Generates candidate permutations and filters them through the verification waterfall."""
    waterfall = EmailVerificationWaterfall()
    verified_leads = []
    
    for org in orgs:
        domain = org.get("website")
        if not domain or domain.startswith("http"):
            domain = domain.replace("https://", "").replace("http://", "").split("/")[0] if domain else f"{org['name'].lower().replace(' ', '')}.com"
        
        # Test a standard operational / engineering role lead
        sample_name = f"Operations Lead"
        patterns = EmailPermutator.generate_patterns("Operations", domain)
        
        best_candidate = None
        for email in patterns[:3]:
            res = waterfall.verify_email(email)
            if res.confidence_score >= 0.4 and not res.is_disposable and res.status != VerificationStatus.BOUNCED_SUPPRESSED:
                best_candidate = {
                    "organization_name": org["name"],
                    "name": f"{org['name']} Engineering / Ops Lead",
                    "role": "Head of Operations / Engineering",
                    "work_email": email,
                    "verification_status": res.status.value,
                    "confidence_score": res.confidence_score,
                    "notes": f"Permutation waterfall verified ({res.details})"
                }
                break
        
        if best_candidate:
            verified_leads.append(best_candidate)

    print(f"[+] Successfully generated and verified {len(verified_leads)} candidate leads.")
    return verified_leads


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
    """Prefect orchestration flow for weekly lead enrichment."""
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
