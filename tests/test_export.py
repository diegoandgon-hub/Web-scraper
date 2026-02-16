"""Tests T7.1-T7.6 for Task 7: Data Export."""

from __future__ import annotations

import csv
import json
from datetime import date
from io import StringIO

import pytest

from job_scraper.db.crud import insert_job, update_filter_status
from job_scraper.db.models import init_db
from job_scraper.export.csv_export import export_csv
from job_scraper.export.json_export import export_json


def _job(**overrides):
    base = {
        "title": "Process Engineer",
        "company": "Acme",
        "location_city": "Geneva",
        "location_canton": "GE",
        "description": "Design processes.",
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


@pytest.fixture
def db_with_jobs(db):
    """DB with 2 passed and 1 rejected job."""
    insert_job(db, _job(url="https://example.com/1"))
    insert_job(db, _job(url="https://example.com/2", title="Automation Engineer"))
    insert_job(db, _job(url="https://example.com/3", title="Rejected Job"))
    update_filter_status(db, 1, "passed", "ok")
    update_filter_status(db, 2, "passed", "ok")
    update_filter_status(db, 3, "rejected", "bad location")
    return db


# ------------------------------------------------------------------
# T7.1 - CSV has correct row count + header + metadata comments
# ------------------------------------------------------------------
class TestT7_1_CsvStructure:
    def test_csv_row_count_and_header(self, db_with_jobs, tmp_path):
        path = str(tmp_path / "out.csv")
        export_csv(db_with_jobs, path, filter_status="passed")

        with open(path, encoding="utf-8") as f:
            lines = f.readlines()

        # 3 metadata comment lines + 1 header + 2 data rows = 6
        comment_lines = [l for l in lines if l.startswith("#")]
        assert len(comment_lines) == 3

        data_lines = [l for l in lines if not l.startswith("#")]
        reader = csv.reader(StringIO("".join(data_lines)))
        rows = list(reader)
        assert rows[0][0] == "id"  # header
        assert len(rows) == 3  # header + 2 passed jobs

    def test_metadata_comments_present(self, db_with_jobs, tmp_path):
        path = str(tmp_path / "out.csv")
        export_csv(db_with_jobs, path, filter_status="passed")

        text = open(path, encoding="utf-8").read()
        assert "# export_date:" in text
        assert "# total_count: 2" in text
        assert "# filter_status: passed" in text


# ------------------------------------------------------------------
# T7.2 - CSV handles commas/newlines in descriptions
# ------------------------------------------------------------------
class TestT7_2_CsvSpecialChars:
    def test_commas_and_newlines_in_description(self, db, tmp_path):
        insert_job(db, _job(
            description="Design, build,\nand optimize processes.",
            url="https://example.com/special",
        ))
        update_filter_status(db, 1, "passed", "ok")

        path = str(tmp_path / "out.csv")
        export_csv(db, path, filter_status="passed")

        with open(path, encoding="utf-8") as f:
            content = f.read()

        # Strip comment lines, parse CSV
        data = "\n".join(l for l in content.splitlines() if not l.startswith("#"))
        reader = csv.DictReader(StringIO(data))
        rows = list(reader)
        assert len(rows) == 1
        assert "Design, build,\nand optimize" in rows[0]["description"]


# ------------------------------------------------------------------
# T7.3 - JSON is valid with correct metadata.total_count
# ------------------------------------------------------------------
class TestT7_3_JsonStructure:
    def test_valid_json_with_metadata(self, db_with_jobs, tmp_path):
        path = str(tmp_path / "out.json")
        export_json(db_with_jobs, path, filter_status="passed")

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        assert "metadata" in data
        assert "jobs" in data
        assert data["metadata"]["total_count"] == 2
        assert data["metadata"]["filter_status"] == "passed"
        assert data["metadata"]["export_date"] == date.today().isoformat()
        assert len(data["jobs"]) == 2


# ------------------------------------------------------------------
# T7.4 - Export with filter_status="passed" excludes rejected jobs
# ------------------------------------------------------------------
class TestT7_4_FilterExclusion:
    def test_csv_excludes_rejected(self, db_with_jobs, tmp_path):
        path = str(tmp_path / "out.csv")
        export_csv(db_with_jobs, path, filter_status="passed")

        with open(path, encoding="utf-8") as f:
            content = f.read()

        assert "Rejected Job" not in content

    def test_json_excludes_rejected(self, db_with_jobs, tmp_path):
        path = str(tmp_path / "out.json")
        export_json(db_with_jobs, path, filter_status="passed")

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        titles = [j["title"] for j in data["jobs"]]
        assert "Rejected Job" not in titles


# ------------------------------------------------------------------
# T7.5 - Non-existent output directory raises clear error
# ------------------------------------------------------------------
class TestT7_5_MissingDirectory:
    def test_csv_raises_on_missing_dir(self, db):
        with pytest.raises(FileNotFoundError, match="does not exist"):
            export_csv(db, "/nonexistent/dir/out.csv")

    def test_json_raises_on_missing_dir(self, db):
        with pytest.raises(FileNotFoundError, match="does not exist"):
            export_json(db, "/nonexistent/dir/out.json")


# ------------------------------------------------------------------
# T7.6 - Default filename contains today's date
# ------------------------------------------------------------------
class TestT7_6_DefaultFilename:
    def test_csv_default_has_date(self, db, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        path = export_csv(db, filter_status="passed")
        assert date.today().isoformat() in path
        assert path.endswith(".csv")

    def test_json_default_has_date(self, db, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        path = export_json(db, filter_status="passed")
        assert date.today().isoformat() in path
        assert path.endswith(".json")
