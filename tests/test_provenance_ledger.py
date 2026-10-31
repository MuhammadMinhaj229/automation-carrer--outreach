"""Tests for local source and claim provenance controls."""
import pytest

from acios.core.repository import CareerRepository


def test_source_claim_review_requires_primary_source_classification(tmp_path):
    repo = CareerRepository(db_path=tmp_path / "provenance.db")
    source_id = repo.record_source_document({
        "url": "https://example.org/about",
        "publisher": "example.org",
        "title": "About the organization",
        "source_type": "UNKNOWN",
        "content_text": "Example organization was founded in 2012.",
        "excerpt": "Example organization was founded in 2012.",
    })
    claim_id = repo.add_claim(
        entity_type="organization",
        entity_key="Example Organization",
        predicate="founded_on",
        claim_value="2012",
        source_id=source_id,
        excerpt="Example organization was founded in 2012.",
        valid_from="2012-01-01",
    )

    with pytest.raises(ValueError, match="official primary source"):
        repo.review_claim(
            claim_id,
            verification_status="VERIFIED_PRIMARY",
            reviewed_by="reviewer",
            review_note="The text appears to support the claim.",
            confidence=0.9,
        )

    repo.classify_source_document(
        source_id,
        source_type="OFFICIAL_PRIMARY",
        reviewed_by="reviewer",
        review_note="Reviewed the issuer's official organization history page.",
    )
    reviewed = repo.review_claim(
        claim_id,
        verification_status="VERIFIED_PRIMARY",
        reviewed_by="reviewer",
        review_note="The official page explicitly states the founding year.",
        confidence=0.95,
    )
    assert reviewed["verification_status"] == "VERIFIED_PRIMARY"
    assert reviewed["source_id"] == source_id
    with repo._conn() as conn:
        source_reviews = conn.execute(
            "SELECT COUNT(*) FROM source_reviews WHERE source_id = ?", (source_id,)
        ).fetchone()[0]
        claim_reviews = conn.execute(
            "SELECT COUNT(*) FROM claim_reviews WHERE claim_id = ?", (claim_id,)
        ).fetchone()[0]
    assert source_reviews == 1
    assert claim_reviews == 1


def test_corroborated_claim_requires_two_distinct_publishers(tmp_path):
    repo = CareerRepository(db_path=tmp_path / "corroboration.db")
    source_a = repo.record_source_document({
        "url": "https://publisher-a.example/story",
        "publisher": "publisher-a.example",
        "title": "Story A",
        "source_type": "INDEPENDENT_SECONDARY",
        "content_text": "Example company opened a facility in 2025.",
    })
    claim_id = repo.add_claim(
        "organization", "Example Company", "facility_opened", "2025",
        source_a, "Example company opened a facility in 2025."
    )
    with pytest.raises(ValueError, match="two named publishers"):
        repo.review_claim(
            claim_id, "CORROBORATED", "reviewer",
            "The same publisher repeats the claim.", 0.7
        )

    source_b = repo.record_source_document({
        "url": "https://publisher-b.example/report",
        "publisher": "publisher-b.example",
        "title": "Independent report",
        "source_type": "INDEPENDENT_SECONDARY",
        "content_text": "Example company opened a facility in 2025.",
    })
    repo.add_claim(
        "organization", "Example Company", "facility_opened", "2025",
        source_b, "Example company opened a facility in 2025."
    )
    # The first claim may now be corroborated by two distinct named publishers.
    reviewed = repo.review_claim(
        claim_id, "CORROBORATED", "reviewer",
        "Two independent publishers support the same dated event.", 0.8
    )
    assert reviewed["verification_status"] == "CORROBORATED"


def test_source_document_deduplicates_by_url_and_content_hash(tmp_path):
    repo = CareerRepository(db_path=tmp_path / "dedupe.db")
    payload = {
        "url": "https://example.org/news",
        "publisher": "example.org",
        "title": "News",
        "content_text": "A fixed source body.",
    }
    first = repo.record_source_document(payload)
    second = repo.record_source_document(payload)
    assert first == second
    assert len(repo.list_source_documents()) == 1


def test_source_urls_reject_embedded_credentials_and_non_http(tmp_path):
    repo = CareerRepository(db_path=tmp_path / "url-policy.db")
    with pytest.raises(ValueError, match="valid HTTP"):
        repo.record_source_document({"url": "file:///etc/passwd"})
    with pytest.raises(ValueError, match="embedded credentials"):
        repo.record_source_document({"url": "https://user:pass@example.org/"})
