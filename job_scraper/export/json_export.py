"""F7.2 — JSON export with metadata and pretty printing."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from job_scraper.db.crud import get_jobs


def _default_filename(filter_status: str) -> str:
    return f"jobs_{filter_status}_{date.today().isoformat()}.json"


def export_json(
    conn,
    output_path: str | None = None,
    filter_status: str = "passed",
) -> str:
    """Export jobs to pretty-printed JSON with metadata.

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

    payload = {
        "metadata": {
            "export_date": date.today().isoformat(),
            "total_count": len(jobs),
            "filter_status": filter_status,
        },
        "jobs": jobs,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    return output_path
