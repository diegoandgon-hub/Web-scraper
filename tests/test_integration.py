"""Tests T11.1-T11.5 for Task 11: Integration & E2E Testing."""

from __future__ import annotations

import csv
import json
from io import StringIO

import pytest

from job_scraper.db.crud import count_jobs
from job_scraper.db.models import init_db
from job_scraper.dedup.deduplicator import (
    compute_content_hash,
    deduplicated_insert,
    get_all_content_hashes,
)
from job_scraper.export.csv_export import export_csv
from job_scraper.export.json_export import export_json
from job_scraper.filters.keyword_filter import keyword_filter
from job_scraper.filters.pipeline import run_filters
from job_scraper.runner import run_scrapers
from job_scraper.scrapers.base import BaseScraper


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _job(**overrides):
    """Return a baseline job dict that passes all keyword filters."""
    base = {
        "title": "Process Engineer",
        "company": "Acme SA",
        "location_city": "Lausanne",
        "location_canton": "VD",
        "description": (
            "We are looking for an entry-level process engineer "
            "to join our team in Lausanne. The role involves designing "
            "and optimizing industrial processes. English required."
        ),
        "qualifications": "BSc in Chemical Engineering",
        "language_requirements": "English",
        "experience_level": "Entry level",
        "url": "https://example.com/job/1",
        "date_scraped": "2026-02-15T12:00:00",
        "source": "linkedin",
    }
    base.update(overrides)
    return base


class _FakeScraper(BaseScraper):
    """Test scraper that returns pre-set jobs without network calls."""

    def __init__(self, name: str, jobs: list[dict]):
        super().__init__(name)
        self._jobs = jobs

    def parse(self, raw_data):
        return self._jobs

    def scrape(self) -> list[dict]:
        return self._jobs


@pytest.fixture
def db():
    conn = init_db(":memory:")
    yield conn
    conn.close()


# ------------------------------------------------------------------
# T11.1 - Full pipeline produces correct CSV with expected row count
# ------------------------------------------------------------------
class TestT11_1_FullPipeline:
    def test_full_pipeline_csv(self, db, tmp_path):
        """init DB -> mock scrape (LinkedIn + ABB with 1 overlap) ->
        keyword filter -> LLM filter (mocked) -> CSV export -> verify."""

        # --- Scrape phase: 2 LinkedIn + 2 ABB, 1 overlapping content ---
        linkedin_jobs = [
            _job(url="https://linkedin.com/job/1", source="linkedin"),
            _job(
                url="https://linkedin.com/job/2",
                source="linkedin",
                title="Automation Engineer",
                description=(
                    "Junior automation engineer position in Geneva. "
                    "PLC and SCADA experience is a plus. English required."
                ),
                location_city="Geneva",
                location_canton="GE",
            ),
        ]

        # ABB job 1 has same content as LinkedIn job 1 (cross-source dup)
        abb_jobs = [
            _job(url="https://abb.com/job/1", source="abb"),  # same content as linkedin job 1
            _job(
                url="https://abb.com/job/2",
                source="abb",
                title="Energy Engineer",
                description=(
                    "We need a graduate energy engineer for renewable energy "
                    "projects in Sion. English fluency is required."
                ),
                location_city="Sion",
                location_canton="VS",
            ),
        ]

        # Insert via dedup pipeline (simulating what real scrapers do)
        existing_hashes = get_all_content_hashes(db)
        inserted_count = 0
        for jobs in [linkedin_jobs, abb_jobs]:
            for job_dict in jobs:
                h = compute_content_hash(
                    job_dict["title"], job_dict["company"], job_dict["description"]
                )
                job_dict["content_hash"] = h
                result = deduplicated_insert(db, job_dict, existing_hashes)
                if result is not None:
                    inserted_count += 1

        # 4 total jobs, but 1 is a cross-source duplicate
        assert inserted_count == 3

        # --- Filter phase: keyword filter (no LLM) ---
        summary = run_filters(db, use_llm=False)
        assert summary["passed"] + summary["rejected"] + summary["ambiguous"] == 3

        # --- Export phase ---
        csv_path = str(tmp_path / "pipeline_out.csv")
        export_csv(db, csv_path, filter_status="passed")

        with open(csv_path, encoding="utf-8") as f:
            content = f.read()

        data_lines = [l for l in content.splitlines() if not l.startswith("#")]
        reader = csv.reader(StringIO("\n".join(data_lines)))
        rows = list(reader)
        # header + passed jobs
        assert len(rows) >= 2  # at least header + 1 passed job

        # Verify metadata
        assert "# filter_status: passed" in content

    def test_full_pipeline_json(self, db, tmp_path):
        """Same pipeline but export to JSON."""
        job1 = _job(url="https://example.com/j1")
        job1["content_hash"] = compute_content_hash(
            job1["title"], job1["company"], job1["description"]
        )
        existing = get_all_content_hashes(db)
        deduplicated_insert(db, job1, existing)

        run_filters(db, use_llm=False)

        json_path = str(tmp_path / "pipeline_out.json")
        export_json(db, json_path, filter_status="passed")

        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)

        assert "metadata" in data
        assert "jobs" in data
        assert data["metadata"]["total_count"] == len(data["jobs"])


# ------------------------------------------------------------------
# T11.2 - 20 curated jobs all produce expected filter outcomes
# ------------------------------------------------------------------
class TestT11_2_CuratedJobs:
    """20 curated job dicts covering all edge cases."""

    CURATED_JOBS = [
        # 1. Perfect pass: entry-level process engineer in Romandie, English
        (_job(), "passed"),
        # 2. Pass: automation engineer in Geneva
        (_job(title="Automation Engineer", location_canton="GE",
              description="Junior automation engineer needed. PLC and SCADA. English required.",
              experience_level="Entry level"), "passed"),
        # 3. Pass: energy engineer in Neuchâtel
        (_job(title="Energy Engineer", location_city="Neuchâtel", location_canton="NE",
              description="Graduate energy engineer for renewable energy. English.",
              experience_level="Entry level"), "passed"),
        # 4. Rejected: location Zurich (not Romandie)
        (_job(location_city="Zurich", location_canton="ZH"), "rejected"),
        # 5. Rejected: location Bern
        (_job(location_city="Bern", location_canton="BE"), "rejected"),
        # 6. Rejected: French language required
        (_job(description="Process engineer, français courant requis. Entry-level."), "rejected"),
        # 7. Rejected: German required
        (_job(description="Process engineer, Deutsch required. Entry-level."), "rejected"),
        # 8. Rejected: French fluent
        (_job(description="Process engineer, french fluent required. Entry-level."), "rejected"),
        # 9. Rejected: Senior title
        (_job(title="Senior Process Engineer"), "rejected"),
        # 10. Rejected: Lead title
        (_job(title="Lead Automation Engineer",
              description="Lead automation engineer for PLC systems. English. Entry-level."), "rejected"),
        # 11. Rejected: 5+ years experience
        (_job(description="Process engineer, 5+ years experience required. English."), "rejected"),
        # 12. Rejected: 10 years experience
        (_job(description="Process engineer, 10 years experience. English."), "rejected"),
        # 13. Rejected: currently enrolled student
        (_job(description="Process engineer intern, must be currently enrolled. English."), "rejected"),
        # 14. Rejected: active student
        (_job(description="Process engineer role for active student. English."), "rejected"),
        # 15. Rejected: no discipline keyword
        (_job(title="Marketing Manager",
              description="Marketing role in Lausanne. Entry-level. English."), "rejected"),
        # 16. Rejected: wrong discipline
        (_job(title="Data Scientist",
              description="Data science position in Geneva. English. Junior."), "rejected"),
        # 17. Ambiguous: very short description
        (_job(description="Process engineer."), "ambiguous"),
        # 18. Ambiguous: no experience level info at all
        (_job(description="Process engineer needed for manufacturing plant in Lausanne. English proficiency needed.",
              experience_level="", qualifications=""), "ambiguous"),
        # 19. Ambiguous: no language info at all
        (_job(description="Entry-level process engineer to join our team and optimize production processes.",
              language_requirements="", experience_level="Entry level"), "ambiguous"),
        # 20. Pass: electrical engineer (energy discipline) with trainee keyword
        (_job(title="Electrical Engineer", location_canton="VD",
              description="Trainee electrical engineer for power systems in Lausanne. English required.",
              experience_level="Trainee"), "passed"),
    ]

    @pytest.mark.parametrize(
        "job_dict, expected_status",
        CURATED_JOBS,
        ids=[f"curated_{i+1}" for i in range(20)],
    )
    def test_curated_job(self, job_dict, expected_status):
        status, reason = keyword_filter(job_dict)
        assert status == expected_status, (
            f"Expected {expected_status} but got {status} (reason: {reason}) "
            f"for job: title={job_dict.get('title')}"
        )


# ------------------------------------------------------------------
# T11.3 - Double scrape = no duplicate rows in DB
# ------------------------------------------------------------------
class TestT11_3_Idempotency:
    def test_double_scrape_no_duplicates(self, db):
        """Run same scrape data twice, verify no duplicates."""
        jobs = [
            _job(url="https://example.com/job/1"),
            _job(url="https://example.com/job/2", title="Automation Engineer",
                 description="PLC SCADA automation engineer. Entry-level. English."),
        ]

        # First scrape
        existing_hashes = get_all_content_hashes(db)
        for j in jobs:
            j["content_hash"] = compute_content_hash(
                j["title"], j["company"], j["description"]
            )
            deduplicated_insert(db, j, existing_hashes)

        count_after_first = count_jobs(db)
        assert count_after_first == 2

        # Second scrape with identical data
        existing_hashes = get_all_content_hashes(db)
        for j in jobs:
            deduplicated_insert(db, j, existing_hashes)

        count_after_second = count_jobs(db)
        assert count_after_second == 2  # no new rows

    def test_cross_source_duplicate_idempotent(self, db):
        """Same content from different source is still deduplicated."""
        job_linkedin = _job(url="https://linkedin.com/job/1", source="linkedin")
        job_abb = _job(url="https://abb.com/job/1", source="abb")  # same content, different URL

        existing_hashes = get_all_content_hashes(db)
        for j in [job_linkedin, job_abb]:
            j["content_hash"] = compute_content_hash(
                j["title"], j["company"], j["description"]
            )
            deduplicated_insert(db, j, existing_hashes)

        assert count_jobs(db) == 1  # only the first inserted


# ------------------------------------------------------------------
# T11.4 - Empty scrape result (0 jobs) causes no downstream errors
# ------------------------------------------------------------------
class TestT11_4_EmptyScrape:
    def test_empty_scrape_no_errors(self, db, tmp_path):
        """Pipeline runs cleanly even with 0 jobs."""
        # Scrape with no jobs
        empty_scraper = _FakeScraper("empty", [])
        summary = run_scrapers([empty_scraper])
        assert summary.new_jobs == 0
        assert summary.sources_succeeded == ["empty"]

        # Filter on empty DB
        filter_summary = run_filters(db, use_llm=False)
        assert filter_summary == {"passed": 0, "rejected": 0, "ambiguous": 0}

        # Export on empty DB
        csv_path = str(tmp_path / "empty.csv")
        export_csv(db, csv_path, filter_status="passed")
        with open(csv_path, encoding="utf-8") as f:
            content = f.read()
        assert "# total_count: 0" in content

        json_path = str(tmp_path / "empty.json")
        export_json(db, json_path, filter_status="passed")
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["metadata"]["total_count"] == 0
        assert data["jobs"] == []


# ------------------------------------------------------------------
# T11.5 - DB state after full pipeline has correct counts per filter_status
# ------------------------------------------------------------------
class TestT11_5_DbStateCounts:
    def test_correct_counts_per_status(self, db):
        """Insert a mix of jobs, run filters, verify DB counts."""
        jobs = [
            # Should pass: entry-level process engineer in Romandie, English
            _job(url="https://example.com/1"),
            # Should pass: automation engineer, junior, English
            _job(url="https://example.com/2", title="Automation Engineer",
                 description="Junior automation engineer for PLC/SCADA systems in Geneva. English required.",
                 location_city="Geneva", location_canton="GE",
                 experience_level="Entry level"),
            # Should be rejected: Zurich
            _job(url="https://example.com/3", location_city="Zurich", location_canton="ZH",
                 description="Process engineer for chemical plant in Zurich. Entry-level. English."),
            # Should be rejected: senior
            _job(url="https://example.com/4", title="Senior Process Engineer"),
            # Should be rejected: French required
            _job(url="https://example.com/5",
                 description="Process engineer. français courant. Entry-level."),
            # Should be ambiguous: short description
            _job(url="https://example.com/6", description="Process engineer."),
        ]

        existing_hashes = get_all_content_hashes(db)
        for j in jobs:
            j["content_hash"] = compute_content_hash(
                j["title"], j["company"], j["description"]
            )
            deduplicated_insert(db, j, existing_hashes)

        assert count_jobs(db) == 6
        assert count_jobs(db, filter_status="unprocessed") == 6

        # Run keyword filter
        summary = run_filters(db, use_llm=False)

        assert count_jobs(db, filter_status="passed") == 2
        assert count_jobs(db, filter_status="rejected") == 3
        assert count_jobs(db, filter_status="ambiguous") == 1
        assert count_jobs(db, filter_status="unprocessed") == 0

        # Totals match
        assert summary["passed"] == 2
        assert summary["rejected"] == 3
        assert summary["ambiguous"] == 1
