"""Tests T6.1-T6.14 for Task 6: Filtering Engine."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from job_scraper.db.crud import get_jobs, insert_job
from job_scraper.db.models import init_db
from job_scraper.filters.keyword_filter import keyword_filter
from job_scraper.filters.llm_filter import _build_user_prompt, llm_filter
from job_scraper.filters.pipeline import run_filters


def _job(**overrides):
    """Return a job dict that passes all keyword filters by default."""
    base = {
        "title": "Process Engineer",
        "company": "Acme",
        "location_city": "Geneva",
        "location_canton": "GE",
        "description": (
            "We are looking for a process engineer to join our team. "
            "Design and optimize chemical processes. English is the working language. "
            "This is an entry-level position for recent graduates."
        ),
        "qualifications": "BSc in Chemical Engineering",
        "language_requirements": "English",
        "experience_level": "Entry level",
        "url": "https://example.com/job/1",
        "date_scraped": "2026-01-15T12:00:00",
        "source": "test",
    }
    base.update(overrides)
    return base


@pytest.fixture
def db():
    conn = init_db(":memory:")
    yield conn
    conn.close()


# ------------------------------------------------------------------
# T6.1 - English process engineer job in Geneva passes all filters
# ------------------------------------------------------------------
class TestT6_1_PassingJob:
    def test_passes_all_checks(self):
        status, reason = keyword_filter(_job())
        assert status == "passed"


# ------------------------------------------------------------------
# T6.2 - Zurich job rejected ("location not in Romandie")
# ------------------------------------------------------------------
class TestT6_2_LocationRejection:
    def test_zurich_rejected(self):
        status, reason = keyword_filter(_job(location_canton="ZH"))
        assert status == "rejected"
        assert "Romandie" in reason

    def test_bern_rejected(self):
        status, reason = keyword_filter(_job(location_canton="BE"))
        assert status == "rejected"


# ------------------------------------------------------------------
# T6.3 - "Francais courant requis" in description -> rejected
# ------------------------------------------------------------------
class TestT6_3_FrenchLanguage:
    def test_francais_courant_rejected(self):
        status, reason = keyword_filter(
            _job(description="Great role. Francais courant requis. Process engineer needed.")
        )
        assert status == "rejected"
        assert "language" in reason.lower()

    def test_français_rejected(self):
        status, reason = keyword_filter(
            _job(description="Process engineer role. Français obligatoire.")
        )
        assert status == "rejected"


# ------------------------------------------------------------------
# T6.4 - "German: fluent" in qualifications -> rejected
# ------------------------------------------------------------------
class TestT6_4_GermanLanguage:
    def test_german_fluent_rejected(self):
        status, reason = keyword_filter(
            _job(qualifications="BSc required. German: fluent")
        )
        assert status == "rejected"
        assert "language" in reason.lower()

    def test_deutsch_rejected(self):
        status, reason = keyword_filter(
            _job(qualifications="Deutsch erforderlich")
        )
        assert status == "rejected"


# ------------------------------------------------------------------
# T6.5 - "5+ years experience" -> rejected (not entry-level)
# ------------------------------------------------------------------
class TestT6_5_SeniorRejection:
    def test_five_plus_years_rejected(self):
        status, reason = keyword_filter(
            _job(description="Process engineer with 5+ years experience required.")
        )
        assert status == "rejected"
        assert "entry-level" in reason.lower() or "senior" in reason.lower()

    def test_senior_title_rejected(self):
        status, reason = keyword_filter(_job(title="Senior Process Engineer"))
        assert status == "rejected"


# ------------------------------------------------------------------
# T6.6 - "Currently enrolled student" internship -> rejected
# ------------------------------------------------------------------
class TestT6_6_EnrollmentRejection:
    def test_currently_enrolled_rejected(self):
        status, reason = keyword_filter(
            _job(description="Process engineering internship. Must be currently enrolled in university.")
        )
        assert status == "rejected"
        assert "enrollment" in reason.lower()

    def test_active_student_rejected(self):
        status, reason = keyword_filter(
            _job(description="Process engineer intern. Active student required.")
        )
        assert status == "rejected"


# ------------------------------------------------------------------
# T6.7 - No language requirements + short description -> ambiguous
# ------------------------------------------------------------------
class TestT6_7_AmbiguousShortDesc:
    def test_short_description_ambiguous(self):
        status, reason = keyword_filter(
            _job(description="Process engineer.", language_requirements="")
        )
        assert status == "ambiguous"
        assert "short" in reason.lower() or "missing" in reason.lower()


# ------------------------------------------------------------------
# T6.8 - Matching title but no experience info -> ambiguous
# ------------------------------------------------------------------
class TestT6_8_AmbiguousNoExperience:
    def test_no_experience_info_ambiguous(self):
        status, reason = keyword_filter(
            _job(
                experience_level="",
                description=(
                    "We need a process engineer for our chemical plant. "
                    "English is the working language. Good opportunity."
                ),
            )
        )
        assert status == "ambiguous"
        assert "experience" in reason.lower()


# ------------------------------------------------------------------
# T6.9 - LLM filter returns pass -> status becomes "passed" (mocked)
# ------------------------------------------------------------------
class TestT6_9_LlmPass:
    @patch("job_scraper.filters.llm_filter.CLAUDE_API_KEY", "test-key")
    @patch("job_scraper.filters.llm_filter.anthropic")
    def test_llm_pass(self, mock_anthropic):
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text='{"pass": true, "reason": "Looks good"}')]
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_msg

        status, reason = llm_filter(_job())
        assert status == "passed"
        assert "Looks good" in reason


# ------------------------------------------------------------------
# T6.10 - LLM filter returns reject -> status becomes "rejected"
# ------------------------------------------------------------------
class TestT6_10_LlmReject:
    @patch("job_scraper.filters.llm_filter.CLAUDE_API_KEY", "test-key")
    @patch("job_scraper.filters.llm_filter.anthropic")
    def test_llm_reject(self, mock_anthropic):
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text='{"pass": false, "reason": "Too senior"}')]
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_msg

        status, reason = llm_filter(_job())
        assert status == "rejected"
        assert "Too senior" in reason


# ------------------------------------------------------------------
# T6.11 - LLM filter API error -> status stays "ambiguous", error logged
# ------------------------------------------------------------------
class TestT6_11_LlmError:
    @patch("job_scraper.filters.llm_filter.CLAUDE_API_KEY", "test-key")
    @patch("job_scraper.filters.llm_filter.anthropic")
    def test_api_error_stays_ambiguous(self, mock_anthropic, caplog):
        mock_anthropic.Anthropic.return_value.messages.create.side_effect = (
            RuntimeError("API down")
        )
        with caplog.at_level(logging.ERROR):
            status, reason = llm_filter(_job())

        assert status == "ambiguous"
        assert "error" in reason.lower()

    def test_no_api_key_stays_ambiguous(self):
        status, reason = llm_filter(_job())
        assert status == "ambiguous"
        assert "no API key" in reason.lower() or "skipped" in reason.lower()


# ------------------------------------------------------------------
# T6.12 - Description truncated to 2000 chars before LLM call
# ------------------------------------------------------------------
class TestT6_12_DescriptionTruncation:
    def test_prompt_truncates_description(self):
        long_desc = "Z" * 5000
        job = _job(description=long_desc)
        prompt = _build_user_prompt(job)
        # The description in the prompt should be at most 2000 chars of Z's
        z_count = prompt.count("Z")
        assert z_count == 2000


# ------------------------------------------------------------------
# T6.13 - Pipeline: 3 jobs (pass, reject, ambiguous->LLM) verified in DB
# ------------------------------------------------------------------
class TestT6_13_Pipeline:
    def test_pipeline_processes_three_jobs(self, db):
        # Job 1: should pass
        insert_job(db, _job(url="https://example.com/1"))
        # Job 2: should be rejected (Zurich)
        insert_job(db, _job(url="https://example.com/2", location_canton="ZH"))
        # Job 3: ambiguous (no experience info)
        insert_job(db, _job(
            url="https://example.com/3",
            experience_level="",
            description=(
                "We need a process engineer for our chemical plant. "
                "English is the working language. Good opportunity."
            ),
        ))

        summary = run_filters(db, use_llm=False)

        assert summary["passed"] == 1
        assert summary["rejected"] == 1
        assert summary["ambiguous"] == 1

        # Verify DB state
        passed = get_jobs(db, filter_status="passed")
        assert len(passed) == 1
        assert passed[0]["url"] == "https://example.com/1"

        rejected = get_jobs(db, filter_status="rejected")
        assert len(rejected) == 1

        ambiguous = get_jobs(db, filter_status="ambiguous")
        assert len(ambiguous) == 1


# ------------------------------------------------------------------
# T6.14 - City "Lausanne" resolves to canton "VD" when canton missing
# ------------------------------------------------------------------
class TestT6_14_CityResolution:
    def test_lausanne_resolves_to_vd(self):
        status, reason = keyword_filter(
            _job(location_city="Lausanne", location_canton=None)
        )
        assert status == "passed"

    def test_zurich_city_rejected(self):
        # Zurich is not in ROMANDIE_CITIES so canton resolves to None,
        # meaning no rejection on location. But let's test with explicit canton.
        status, reason = keyword_filter(
            _job(location_city="Zurich", location_canton="ZH")
        )
        assert status == "rejected"
        assert "Romandie" in reason
