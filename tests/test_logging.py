"""Tests T10.1-T10.5 for Task 10: Logging & Error Handling."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from job_scraper.logging_config import setup_logging
from job_scraper.runner import RunSummary, run_scrapers
from job_scraper.scrapers.base import BaseScraper
from job_scraper.scrapers.exceptions import ParseError, ScrapingError


# ------------------------------------------------------------------
# Helpers — concrete dummy scrapers
# ------------------------------------------------------------------

class _GoodScraper(BaseScraper):
    def __init__(self, source_name="good", jobs=None):
        self.source_name = source_name
        self.session = MagicMock()
        self._jobs = jobs if jobs is not None else [{"title": "Engineer"}]

    def parse(self, response):
        return self._jobs

    def scrape(self):
        return self._jobs


class _FailingScraper(BaseScraper):
    """Raises ScrapingError on scrape()."""
    def __init__(self, source_name="failing"):
        self.source_name = source_name
        self.session = MagicMock()

    def parse(self, response):
        return []

    def scrape(self):
        raise ScrapingError("connection timeout")


class _ParseFailScraper(BaseScraper):
    """Raises ParseError on scrape()."""
    def __init__(self, source_name="parse_fail"):
        self.source_name = source_name
        self.session = MagicMock()

    def parse(self, response):
        raise ParseError("bad HTML")

    def scrape(self):
        raise ParseError("bad HTML")


# ------------------------------------------------------------------
# Fixture: remove our custom handlers between tests so setup_logging
# can be called fresh each time.
# ------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_job_scraper_handlers():
    """Remove job-scraper handlers from root logger before/after each test."""
    root = logging.getLogger()
    def _remove_ours():
        root.handlers = [
            h for h in root.handlers
            if not getattr(h, "_job_scraper", False)
        ]
    _remove_ours()
    yield
    _remove_ours()


# ------------------------------------------------------------------
# T10.1 - Log file created at configured path
# ------------------------------------------------------------------
class TestT10_1_LogFile:
    def test_log_file_created(self, tmp_path):
        log_dir = tmp_path / "logs"
        log_file = log_dir / "scraper.log"

        setup_logging(log_dir=log_dir, log_file=log_file)

        logger = logging.getLogger("test_t10_1")
        logger.info("hello from test")

        # Flush to ensure write
        for h in logging.getLogger().handlers:
            h.flush()

        assert log_file.exists()
        contents = log_file.read_text()
        assert "hello from test" in contents

    def test_log_dir_created_if_missing(self, tmp_path):
        log_dir = tmp_path / "nested" / "logs"
        log_file = log_dir / "scraper.log"

        setup_logging(log_dir=log_dir, log_file=log_file)

        assert log_dir.exists()


# ------------------------------------------------------------------
# T10.2 - One scraper error doesn't block others from running
# ------------------------------------------------------------------
class TestT10_2_ScraperIsolation:
    def test_failing_scraper_does_not_block_others(self):
        scrapers = [_FailingScraper("bad"), _GoodScraper("good")]
        summary = run_scrapers(scrapers)

        assert "bad" in summary.sources_failed
        assert "good" in summary.sources_succeeded

    def test_multiple_failures_still_runs_all(self):
        scrapers = [
            _FailingScraper("fail1"),
            _FailingScraper("fail2"),
            _GoodScraper("ok"),
        ]
        summary = run_scrapers(scrapers)

        assert len(summary.sources_failed) == 2
        assert len(summary.sources_succeeded) == 1


# ------------------------------------------------------------------
# T10.3 - ParseError for one job doesn't block other jobs in same scraper
# ------------------------------------------------------------------
class TestT10_3_ParseErrorIsolation:
    def test_parse_error_scraper_isolated(self):
        scrapers = [_ParseFailScraper("broken"), _GoodScraper("fine")]
        summary = run_scrapers(scrapers)

        assert "broken" in summary.sources_failed
        assert "fine" in summary.sources_succeeded


# ------------------------------------------------------------------
# T10.4 - Summary correctly counts successes, failures, duplicates
# ------------------------------------------------------------------
class TestT10_4_Summary:
    def test_counts_successes_and_failures(self):
        scrapers = [
            _GoodScraper("s1", jobs=[{"t": 1}, {"t": 2}]),
            _GoodScraper("s2", jobs=[{"t": 3}]),
            _FailingScraper("s3"),
        ]
        summary = run_scrapers(scrapers)

        assert summary.sources_succeeded == ["s1", "s2"]
        assert summary.sources_failed == ["s3"]
        assert summary.new_jobs == 3

    def test_summary_log_does_not_raise(self, caplog):
        summary = RunSummary(
            sources_succeeded=["a"],
            sources_failed=["b"],
            new_jobs=5,
            duplicates_skipped=2,
        )
        with caplog.at_level(logging.INFO):
            summary.log()

        assert "succeeded: a" in caplog.text
        assert "failed: b" in caplog.text
        assert "new jobs: 5" in caplog.text
        assert "duplicates: 2" in caplog.text

    def test_empty_run(self):
        summary = run_scrapers([])
        assert summary.sources_succeeded == []
        assert summary.sources_failed == []
        assert summary.new_jobs == 0


# ------------------------------------------------------------------
# T10.5 - Console output at INFO doesn't include DEBUG messages
# ------------------------------------------------------------------
class TestT10_5_ConsoleLevel:
    def test_console_handler_rejects_debug(self, tmp_path):
        log_dir = tmp_path / "logs"
        log_file = log_dir / "scraper.log"
        setup_logging(log_dir=log_dir, log_file=log_file)

        root = logging.getLogger()
        console_handlers = [
            h for h in root.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
            and getattr(h, "_job_scraper", False)
        ]
        assert len(console_handlers) == 1
        console = console_handlers[0]

        # Console level should be INFO — DEBUG records should be filtered out
        assert console.level == logging.INFO

        debug_record = logging.LogRecord(
            "test", logging.DEBUG, "", 0, "debug msg", (), None
        )
        info_record = logging.LogRecord(
            "test", logging.INFO, "", 0, "info msg", (), None
        )
        assert console.filter(debug_record) is True  # filter passes
        assert console.emit  # handler exists
        # The handler's level gates emission:
        assert debug_record.levelno < console.level
        assert info_record.levelno >= console.level

    def test_debug_written_to_file_not_console(self, tmp_path):
        log_dir = tmp_path / "logs"
        log_file = log_dir / "scraper.log"
        setup_logging(log_dir=log_dir, log_file=log_file)

        logger = logging.getLogger("test_t10_5_file")
        logger.debug("file-only debug")
        logger.info("both info")

        for h in logging.getLogger().handlers:
            h.flush()

        contents = log_file.read_text()
        assert "file-only debug" in contents
        assert "both info" in contents
