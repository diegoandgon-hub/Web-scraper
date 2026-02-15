"""Tests T2.1-T2.8 for Task 2: Database Layer."""

import sqlite3

import pytest

from job_scraper.db.models import init_db
from job_scraper.db.crud import (
    count_jobs,
    get_all_content_hashes,
    get_jobs,
    insert_job,
    job_exists,
    update_filter_status,
)


def _make_job(**overrides):
    """Return a minimal valid job dict, with optional overrides."""
    base = {
        "title": "Engineer",
        "company": "Acme",
        "url": "https://example.com/job/1",
        "date_scraped": "2026-01-15T12:00:00",
        "source": "test",
    }
    base.update(overrides)
    return base


@pytest.fixture
def db():
    """Yield an in-memory database connection with the schema initialized."""
    conn = init_db(":memory:")
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# T2.1 - init_db() creates the jobs table; calling twice doesn't error
# ---------------------------------------------------------------------------
class TestT2_1_InitDb:
    def test_creates_jobs_table(self):
        conn = init_db(":memory:")
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_calling_twice_does_not_error(self):
        conn = init_db(":memory:")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS jobs "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "title TEXT NOT NULL, company TEXT NOT NULL, "
            "location_city TEXT, location_canton TEXT, "
            "description TEXT, qualifications TEXT, "
            "language_requirements TEXT, experience_level TEXT, "
            "deadline TEXT, url TEXT NOT NULL UNIQUE, "
            "date_posted TEXT, date_scraped TEXT NOT NULL, "
            "source TEXT NOT NULL, "
            "filter_status TEXT DEFAULT 'unprocessed', "
            "filter_reason TEXT, content_hash TEXT)"
        )
        conn.commit()
        conn.close()

    def test_calling_init_db_twice_on_same_path(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        conn1 = init_db(db_path)
        conn1.close()
        conn2 = init_db(db_path)
        cursor = conn2.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'"
        )
        assert cursor.fetchone() is not None
        conn2.close()

    def test_schema_has_expected_columns(self):
        conn = init_db(":memory:")
        cursor = conn.execute("PRAGMA table_info(jobs)")
        columns = {row[1] for row in cursor.fetchall()}
        expected = {
            "id", "title", "company", "location_city", "location_canton",
            "description", "qualifications", "language_requirements",
            "experience_level", "deadline", "url", "date_posted",
            "date_scraped", "source", "filter_status", "filter_reason",
            "content_hash",
        }
        assert columns == expected
        conn.close()

    def test_url_column_is_unique(self):
        conn = init_db(":memory:")
        conn.execute(
            "INSERT INTO jobs (title, company, url, date_scraped, source) "
            "VALUES ('Dev', 'Co', 'https://example.com/1', '2026-01-01T00:00:00', 'test')"
        )
        try:
            conn.execute(
                "INSERT INTO jobs (title, company, url, date_scraped, source) "
                "VALUES ('Dev2', 'Co2', 'https://example.com/1', '2026-01-02T00:00:00', 'test')"
            )
            conn.commit()
            assert False, "Expected IntegrityError for duplicate URL"
        except sqlite3.IntegrityError:
            pass
        conn.close()

    def test_filter_status_defaults_to_unprocessed(self):
        conn = init_db(":memory:")
        conn.execute(
            "INSERT INTO jobs (title, company, url, date_scraped, source) "
            "VALUES ('Dev', 'Co', 'https://example.com/1', '2026-01-01T00:00:00', 'test')"
        )
        conn.commit()
        row = conn.execute("SELECT filter_status FROM jobs WHERE id=1").fetchone()
        assert row[0] == "unprocessed"
        conn.close()

    def test_uses_in_memory_sqlite(self):
        """T2.8 — tests use in-memory SQLite (:memory:)."""
        conn = init_db(":memory:")
        assert conn is not None
        conn.close()


# ---------------------------------------------------------------------------
# T2.2 - insert_job() returns valid id
# ---------------------------------------------------------------------------
class TestT2_2_InsertJob:
    def test_returns_valid_id(self, db):
        job_id = insert_job(db, _make_job())
        assert isinstance(job_id, int)
        assert job_id > 0

    def test_inserts_all_fields(self, db):
        job = _make_job(
            location_city="Geneva",
            location_canton="GE",
            description="A great role",
            qualifications="BSc",
            language_requirements="French",
            experience_level="entry",
            deadline="2026-06-01",
            date_posted="2026-01-10",
            filter_status="unprocessed",
            filter_reason=None,
            content_hash="abc123",
        )
        job_id = insert_job(db, job)
        row = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        assert row["title"] == "Engineer"
        assert row["location_canton"] == "GE"
        assert row["content_hash"] == "abc123"


# ---------------------------------------------------------------------------
# T2.3 - Duplicate URL insert handled gracefully (returns None or skips)
# ---------------------------------------------------------------------------
class TestT2_3_DuplicateUrl:
    def test_duplicate_url_returns_none(self, db):
        insert_job(db, _make_job())
        result = insert_job(db, _make_job(title="Different Title"))
        assert result is None

    def test_original_row_unchanged_after_duplicate(self, db):
        insert_job(db, _make_job())
        insert_job(db, _make_job(title="Different Title"))
        row = db.execute("SELECT title FROM jobs WHERE url = ?",
                         (_make_job()["url"],)).fetchone()
        assert row["title"] == "Engineer"


# ---------------------------------------------------------------------------
# T2.4 - job_exists() returns correct bool
# ---------------------------------------------------------------------------
class TestT2_4_JobExists:
    def test_returns_true_for_existing_url(self, db):
        insert_job(db, _make_job())
        assert job_exists(db, "https://example.com/job/1") is True

    def test_returns_false_for_missing_url(self, db):
        assert job_exists(db, "https://example.com/nonexistent") is False


# ---------------------------------------------------------------------------
# T2.5 - get_jobs(filter_status="passed") returns only matching rows
# ---------------------------------------------------------------------------
class TestT2_5_GetJobs:
    def test_filter_by_status(self, db):
        insert_job(db, _make_job(url="https://example.com/1"))
        insert_job(db, _make_job(url="https://example.com/2"))
        update_filter_status(db, 1, "passed", "matches")
        update_filter_status(db, 2, "rejected", "no match")

        passed = get_jobs(db, filter_status="passed")
        assert len(passed) == 1
        assert passed[0]["url"] == "https://example.com/1"

    def test_filter_by_source(self, db):
        insert_job(db, _make_job(url="https://example.com/1", source="linkedin"))
        insert_job(db, _make_job(url="https://example.com/2", source="abb"))

        results = get_jobs(db, source="abb")
        assert len(results) == 1
        assert results[0]["source"] == "abb"

    def test_no_filter_returns_all(self, db):
        insert_job(db, _make_job(url="https://example.com/1"))
        insert_job(db, _make_job(url="https://example.com/2"))
        assert len(get_jobs(db)) == 2

    def test_combined_filters(self, db):
        insert_job(db, _make_job(url="https://example.com/1", source="linkedin"))
        insert_job(db, _make_job(url="https://example.com/2", source="abb"))
        insert_job(db, _make_job(url="https://example.com/3", source="linkedin"))
        update_filter_status(db, 1, "passed", None)
        update_filter_status(db, 3, "passed", None)

        results = get_jobs(db, filter_status="passed", source="linkedin")
        assert len(results) == 2


# ---------------------------------------------------------------------------
# T2.6 - update_filter_status() changes the correct row
# ---------------------------------------------------------------------------
class TestT2_6_UpdateFilterStatus:
    def test_updates_correct_row(self, db):
        insert_job(db, _make_job(url="https://example.com/1"))
        insert_job(db, _make_job(url="https://example.com/2"))

        update_filter_status(db, 1, "passed", "keyword match")

        row1 = db.execute("SELECT filter_status, filter_reason FROM jobs WHERE id=1").fetchone()
        row2 = db.execute("SELECT filter_status FROM jobs WHERE id=2").fetchone()
        assert row1["filter_status"] == "passed"
        assert row1["filter_reason"] == "keyword match"
        assert row2["filter_status"] == "unprocessed"

    def test_reason_can_be_none(self, db):
        insert_job(db, _make_job())
        update_filter_status(db, 1, "rejected", None)
        row = db.execute("SELECT filter_reason FROM jobs WHERE id=1").fetchone()
        assert row["filter_reason"] is None


# ---------------------------------------------------------------------------
# T2.7 - count_jobs() returns accurate count
# ---------------------------------------------------------------------------
class TestT2_7_CountJobs:
    def test_count_all(self, db):
        assert count_jobs(db) == 0
        insert_job(db, _make_job(url="https://example.com/1"))
        insert_job(db, _make_job(url="https://example.com/2"))
        assert count_jobs(db) == 2

    def test_count_by_filter_status(self, db):
        insert_job(db, _make_job(url="https://example.com/1"))
        insert_job(db, _make_job(url="https://example.com/2"))
        update_filter_status(db, 1, "passed", None)

        assert count_jobs(db, filter_status="passed") == 1
        assert count_jobs(db, filter_status="unprocessed") == 1
        assert count_jobs(db, filter_status="rejected") == 0


# ---------------------------------------------------------------------------
# T2.8 - All tests use in-memory SQLite (covered by the db fixture above)
# ---------------------------------------------------------------------------
class TestT2_8_InMemory:
    def test_db_fixture_is_in_memory(self, db):
        """Verify the shared fixture uses :memory:."""
        # In-memory databases report an empty string for the database filename
        row = db.execute("PRAGMA database_list").fetchone()
        assert row["file"] == ""


# ---------------------------------------------------------------------------
# get_all_content_hashes()
# ---------------------------------------------------------------------------
class TestGetAllContentHashes:
    def test_returns_empty_set_initially(self, db):
        assert get_all_content_hashes(db) == set()

    def test_returns_non_null_hashes(self, db):
        insert_job(db, _make_job(url="https://example.com/1", content_hash="hash_a"))
        insert_job(db, _make_job(url="https://example.com/2", content_hash="hash_b"))
        insert_job(db, _make_job(url="https://example.com/3"))  # no hash

        hashes = get_all_content_hashes(db)
        assert hashes == {"hash_a", "hash_b"}
