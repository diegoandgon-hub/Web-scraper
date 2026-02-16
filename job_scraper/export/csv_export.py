"""F7.1 — CSV export with metadata comments and proper quoting."""

from __future__ import annotations

import csv
import io
from datetime import date
from pathlib import Path

from job_scraper.db.crud import get_jobs

_COLUMNS = [
    "id", "title", "company", "location_city", "location_canton",
    "description", "qualifications", "language_requirements",
    "experience_level", "deadline", "url", "date_posted",
    "date_scraped", "source", "filter_status", "filter_reason",
    "content_hash",
]


def _default_filename(filter_status: str) -> str:
    return f"jobs_{filter_status}_{date.today().isoformat()}.csv"


def export_csv(
    conn,
    output_path: str | None = None,
    filter_status: str = "passed",
) -> str:
    """Export jobs to CSV with metadata header comments.

    Args:
        conn: SQLite database connection.
        output_path: File path to write. If None, uses default filename
                     in the current directory.
        filter_status: Only export jobs with this status.

    Returns:
        The path that was written to.

    Raises:
        FileNotFoundError: If the parent directory does not exist.
    """
    if output_path is None:
        output_path = _default_filename(filter_status)

    parent = Path(output_path).parent
    if not parent.exists():
        raise FileNotFoundError(f"Output directory does not exist: {parent}")

    jobs = get_jobs(conn, filter_status=filter_status)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        # Metadata comments (F7.3)
        f.write(f"# export_date: {date.today().isoformat()}\n")
        f.write(f"# total_count: {len(jobs)}\n")
        f.write(f"# filter_status: {filter_status}\n")

        writer = csv.DictWriter(
            f, fieldnames=_COLUMNS, extrasaction="ignore", quoting=csv.QUOTE_ALL
        )
        writer.writeheader()
        for job in jobs:
            writer.writerow(job)

    return output_path
