"""Tests T9.1-T9.6 for Task 9: Duplicate Detection."""

import pytest

from job_scraper.db.crud import insert_job
from job_scraper.db.models import init_db
from job_scraper.dedup.deduplicator import (
    compute_content_hash,
    deduplicated_insert,
    is_duplicate,
)


def _make_job(**overrides):
    base = {
        "title": "Process Engineer",
        "company": "Acme Corp",
        "url": "https://example.com/job/1",
        "date_scraped": "2026-01-15T12:00:00",
        "source": "test",
        "description": "Design and optimize chemical processes.",
    }
    base.update(overrides)
    return base


@pytest.fixture
def db():
    conn = init_db(":memory:")
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# T9.1 - Identical jobs produce same hash
# ---------------------------------------------------------------------------
class TestT9_1_IdenticalHash:
    def test_same_inputs_same_hash(self):
        h1 = compute_content_hash("Process Engineer", "Acme", "Design processes")
        h2 = compute_content_hash("Process Engineer", "Acme", "Design processes")
        assert h1 == h2

    def test_hash_is_64_char_hex(self):
        h = compute_content_hash("Title", "Company", "Description")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# ---------------------------------------------------------------------------
# T9.2 - Different titles produce different hashes
# ---------------------------------------------------------------------------
class TestT9_2_DifferentHash:
    def test_different_title(self):
        h1 = compute_content_hash("Process Engineer", "Acme", "Desc")
        h2 = compute_content_hash("Automation Engineer", "Acme", "Desc")
        assert h1 != h2

    def test_different_company(self):
        h1 = compute_content_hash("Engineer", "Acme", "Desc")
        h2 = compute_content_hash("Engineer", "Globex", "Desc")
        assert h1 != h2

    def test_different_description(self):
        h1 = compute_content_hash("Engineer", "Acme", "Design processes")
        h2 = compute_content_hash("Engineer", "Acme", "Manage projects")
        assert h1 != h2


# ---------------------------------------------------------------------------
# T9.3 - Minor whitespace differences produce same hash (normalization)
# ---------------------------------------------------------------------------
class TestT9_3_Normalization:
    def test_extra_whitespace_ignored(self):
        h1 = compute_content_hash("Process Engineer", "Acme", "Design processes")
        h2 = compute_content_hash("Process  Engineer", "Acme", "Design  processes")
        assert h1 == h2

    def test_leading_trailing_whitespace_ignored(self):
        h1 = compute_content_hash("Process Engineer", "Acme", "Design processes")
        h2 = compute_content_hash("  Process Engineer  ", "  Acme  ", "  Design processes  ")
        assert h1 == h2

    def test_case_insensitive(self):
        h1 = compute_content_hash("Process Engineer", "Acme", "Design processes")
        h2 = compute_content_hash("PROCESS ENGINEER", "ACME", "DESIGN PROCESSES")
        assert h1 == h2

    def test_punctuation_ignored(self):
        h1 = compute_content_hash("Process Engineer", "Acme Corp", "Design processes")
        h2 = compute_content_hash("Process Engineer!", "Acme Corp.", "Design processes,")
        assert h1 == h2


# ---------------------------------------------------------------------------
# T9.4 - is_duplicate() returns True when hash in existing set
# ---------------------------------------------------------------------------
class TestT9_4_IsDuplicate:
    def test_returns_true_when_hash_exists(self):
        h = compute_content_hash("Engineer", "Acme", "Desc")
        assert is_duplicate(h, {h}) is True

    def test_returns_false_when_hash_missing(self):
        h = compute_content_hash("Engineer", "Acme", "Desc")
        assert is_duplicate(h, set()) is False


# ---------------------------------------------------------------------------
# T9.5 - Cross-source duplicate detected (same content, different URLs)
# ---------------------------------------------------------------------------
class TestT9_5_CrossSource:
    def test_cross_source_duplicate_skipped(self, db):
        content_hash = compute_content_hash("Engineer", "Acme", "Design processes")
        job1 = _make_job(
            url="https://linkedin.com/jobs/1",
            source="linkedin",
            content_hash=content_hash,
        )
        job2 = _make_job(
            url="https://acme.com/careers/1",
            source="acme",
            content_hash=content_hash,
        )

        hashes = set()
        id1 = deduplicated_insert(db, job1, hashes)
        id2 = deduplicated_insert(db, job2, hashes)

        assert id1 is not None
        assert id2 is None  # caught by content hash


# ---------------------------------------------------------------------------
# T9.6 - URL duplicate caught at DB insert level
# ---------------------------------------------------------------------------
class TestT9_6_UrlDuplicate:
    def test_same_url_skipped(self, db):
        job = _make_job()
        hashes = set()
        id1 = deduplicated_insert(db, job, hashes)
        id2 = deduplicated_insert(db, job, hashes)

        assert id1 is not None
        assert id2 is None
