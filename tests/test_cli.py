"""Tests T8.1-T8.8 for Task 8: CLI Interface."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from job_scraper.cli import main, build_parser


# ------------------------------------------------------------------
# T8.1 - `init` creates database file at configured path
# ------------------------------------------------------------------
class TestT8_1_Init:
    def test_init_creates_db_and_output_dir(self, tmp_path, monkeypatch):
        db_path = tmp_path / "jobs.db"
        out_dir = tmp_path / "output"
        monkeypatch.setattr("job_scraper.cli.DATABASE_PATH", db_path)
        monkeypatch.setattr("job_scraper.cli.OUTPUT_DIR", out_dir)

        rc = main(["init"])

        assert rc == 0
        assert db_path.exists()
        assert out_dir.exists()

    def test_init_is_idempotent(self, tmp_path, monkeypatch):
        db_path = tmp_path / "jobs.db"
        out_dir = tmp_path / "output"
        monkeypatch.setattr("job_scraper.cli.DATABASE_PATH", db_path)
        monkeypatch.setattr("job_scraper.cli.OUTPUT_DIR", out_dir)

        main(["init"])
        rc = main(["init"])  # second call should not fail

        assert rc == 0


# ------------------------------------------------------------------
# T8.2 - `scrape --source jobup` calls JobUpScraper (mocked)
# ------------------------------------------------------------------
class TestT8_2_ScrapeSingle:
    @patch("job_scraper.cli.run_scrapers")
    def test_scrape_source_jobup(self, mock_run):
        mock_run.return_value = MagicMock(
            sources_succeeded=["jobup"], sources_failed=[], new_jobs=5
        )
        rc = main(["scrape", "--source", "jobup"])

        assert rc == 0
        mock_run.assert_called_once()
        scrapers = mock_run.call_args[0][0]
        assert len(scrapers) == 1
        assert scrapers[0].__class__.__name__ == "JobUpScraper"


# ------------------------------------------------------------------
# T8.3 - `scrape --all` calls all registered scrapers
# ------------------------------------------------------------------
class TestT8_3_ScrapeAll:
    @patch("job_scraper.cli.run_scrapers")
    def test_scrape_all(self, mock_run):
        mock_run.return_value = MagicMock(
            sources_succeeded=["jobup", "abb", "sicpa", "alpiq", "cern", "hitachi"],
            sources_failed=[],
            new_jobs=20,
        )
        rc = main(["scrape", "--all"])

        assert rc == 0
        mock_run.assert_called_once()
        scrapers = mock_run.call_args[0][0]
        assert len(scrapers) == 6
        names = sorted(s.__class__.__name__ for s in scrapers)
        assert names == ["ABBScraper", "AlpiqScraper", "CERNScraper", "HitachiScraper", "JobUpScraper", "SICPAScraper"]


# ------------------------------------------------------------------
# T8.4 - `filter` without `--llm` does not instantiate LLMFilter
# ------------------------------------------------------------------
class TestT8_4_FilterNoLLM:
    @patch("job_scraper.cli.run_filters")
    @patch("job_scraper.cli.init_db")
    def test_filter_no_llm(self, mock_init_db, mock_run_filters):
        mock_conn = MagicMock()
        mock_init_db.return_value = mock_conn
        mock_run_filters.return_value = {"passed": 2, "rejected": 1, "ambiguous": 0}

        rc = main(["filter"])

        assert rc == 0
        mock_run_filters.assert_called_once_with(mock_conn, use_llm=False)


# ------------------------------------------------------------------
# T8.5 - `filter --llm` processes ambiguous jobs through LLMFilter
# ------------------------------------------------------------------
class TestT8_5_FilterWithLLM:
    @patch("job_scraper.cli.run_filters")
    @patch("job_scraper.cli.init_db")
    def test_filter_with_llm(self, mock_init_db, mock_run_filters):
        mock_conn = MagicMock()
        mock_init_db.return_value = mock_conn
        mock_run_filters.return_value = {"passed": 3, "rejected": 1, "ambiguous": 1}

        rc = main(["filter", "--llm"])

        assert rc == 0
        mock_run_filters.assert_called_once_with(mock_conn, use_llm=True)


# ------------------------------------------------------------------
# T8.6 - `export --format json --status all` produces correct output
# ------------------------------------------------------------------
class TestT8_6_ExportAll:
    def test_export_json_all(self, tmp_path, monkeypatch):
        from job_scraper.db.crud import insert_job, update_filter_status
        from job_scraper.db.models import init_db

        db_path = tmp_path / "jobs.db"
        conn = init_db(str(db_path))
        insert_job(conn, {
            "title": "Engineer A", "company": "Co", "location_city": "Geneva",
            "location_canton": "GE", "description": "Desc",
            "url": "https://example.com/1", "date_scraped": "2026-01-15T12:00:00",
            "source": "test",
        })
        insert_job(conn, {
            "title": "Engineer B", "company": "Co", "location_city": "Lausanne",
            "location_canton": "VD", "description": "Desc",
            "url": "https://example.com/2", "date_scraped": "2026-01-15T12:00:00",
            "source": "test",
        })
        update_filter_status(conn, 1, "passed", "ok")
        update_filter_status(conn, 2, "rejected", "bad")
        conn.close()

        monkeypatch.setattr("job_scraper.cli.DATABASE_PATH", db_path)
        out_file = str(tmp_path / "all.json")

        rc = main(["export", "--format", "json", "--status", "all", "--output", out_file])

        assert rc == 0
        with open(out_file, encoding="utf-8") as f:
            data = json.load(f)

        assert data["metadata"]["total_count"] == 2
        assert data["metadata"]["filter_status"] == "all"
        assert len(data["jobs"]) == 2

    def test_export_csv_passed(self, tmp_path, monkeypatch):
        from job_scraper.db.crud import insert_job, update_filter_status
        from job_scraper.db.models import init_db

        db_path = tmp_path / "jobs.db"
        conn = init_db(str(db_path))
        insert_job(conn, {
            "title": "Engineer", "company": "Co", "location_city": "Geneva",
            "location_canton": "GE", "description": "Desc",
            "url": "https://example.com/1", "date_scraped": "2026-01-15T12:00:00",
            "source": "test",
        })
        update_filter_status(conn, 1, "passed", "ok")
        conn.close()

        monkeypatch.setattr("job_scraper.cli.DATABASE_PATH", db_path)
        out_file = str(tmp_path / "out.csv")

        rc = main(["export", "--format", "csv", "--status", "passed", "--output", out_file])

        assert rc == 0
        content = open(out_file, encoding="utf-8").read()
        assert "Engineer" in content


# ------------------------------------------------------------------
# T8.7 - `status` prints correct counts
# ------------------------------------------------------------------
class TestT8_7_Status:
    def test_status_prints_counts(self, tmp_path, monkeypatch, capsys):
        from job_scraper.db.crud import insert_job, update_filter_status
        from job_scraper.db.models import init_db

        db_path = tmp_path / "jobs.db"
        conn = init_db(str(db_path))
        insert_job(conn, {
            "title": "Eng A", "company": "Co", "location_city": "Geneva",
            "location_canton": "GE", "description": "D",
            "url": "https://example.com/1", "date_scraped": "2026-01-15T12:00:00",
            "source": "jobup",
        })
        insert_job(conn, {
            "title": "Eng B", "company": "Co", "location_city": "Lausanne",
            "location_canton": "VD", "description": "D",
            "url": "https://example.com/2", "date_scraped": "2026-01-16T12:00:00",
            "source": "abb",
        })
        update_filter_status(conn, 1, "passed", "ok")
        update_filter_status(conn, 2, "rejected", "bad")
        conn.close()

        monkeypatch.setattr("job_scraper.cli.DATABASE_PATH", db_path)

        rc = main(["status"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "Total jobs: 2" in out
        assert "Passed: 1" in out
        assert "Rejected: 1" in out
        assert "jobup: 1" in out
        assert "abb: 1" in out


# ------------------------------------------------------------------
# T8.8 - Unknown command prints help and exits with code 1
# ------------------------------------------------------------------
class TestT8_8_UnknownCommand:
    def test_no_command_returns_1(self, capsys):
        rc = main([])
        assert rc == 1

    def test_no_command_prints_help(self, capsys):
        main([])
        out = capsys.readouterr().out
        assert "usage:" in out.lower() or "job-scraper" in out


# ------------------------------------------------------------------
# Extra: build_parser returns valid parser
# ------------------------------------------------------------------
class TestBuildParser:
    def test_parser_has_subcommands(self):
        parser = build_parser()
        # Check that parsing known subcommands does not raise
        args = parser.parse_args(["init"])
        assert args.command == "init"

        args = parser.parse_args(["scrape", "--all"])
        assert args.command == "scrape"
        assert args.all is True

        args = parser.parse_args(["export", "--format", "json", "--status", "all"])
        assert args.command == "export"
        assert args.format == "json"
        assert args.status == "all"
