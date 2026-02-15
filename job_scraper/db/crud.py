"""CRUD operations for the jobs table."""

from __future__ import annotations

import sqlite3


# Columns that can be inserted (everything except auto-increment id)
_INSERT_COLUMNS = [
    "title", "company", "location_city", "location_canton",
    "description", "qualifications", "language_requirements",
    "experience_level", "deadline", "url", "date_posted",
    "date_scraped", "source", "filter_status", "filter_reason",
    "content_hash",
]


def insert_job(conn: sqlite3.Connection, job_dict: dict) -> int | None:
    """Insert a job row and return its id, or None if the URL already exists."""
    cols = [c for c in _INSERT_COLUMNS if c in job_dict]
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO jobs ({', '.join(cols)}) VALUES ({placeholders})"
    try:
        cursor = conn.execute(sql, [job_dict[c] for c in cols])
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None


def job_exists(conn: sqlite3.Connection, url: str) -> bool:
    """Return True if a job with the given URL already exists."""
    row = conn.execute("SELECT 1 FROM jobs WHERE url = ?", (url,)).fetchone()
    return row is not None


def get_jobs(
    conn: sqlite3.Connection,
    filter_status: str | None = None,
    source: str | None = None,
) -> list[dict]:
    """Return jobs matching optional filter_status and/or source filters."""
    clauses: list[str] = []
    params: list[str] = []
    if filter_status is not None:
        clauses.append("filter_status = ?")
        params.append(filter_status)
    if source is not None:
        clauses.append("source = ?")
        params.append(source)

    sql = "SELECT * FROM jobs"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)

    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def update_filter_status(
    conn: sqlite3.Connection, job_id: int, status: str, reason: str | None = None
) -> None:
    """Update the filter_status (and optionally filter_reason) for a job."""
    conn.execute(
        "UPDATE jobs SET filter_status = ?, filter_reason = ? WHERE id = ?",
        (status, reason, job_id),
    )
    conn.commit()


def get_all_content_hashes(conn: sqlite3.Connection) -> set[str]:
    """Return the set of all non-null content_hash values in the database."""
    rows = conn.execute(
        "SELECT content_hash FROM jobs WHERE content_hash IS NOT NULL"
    ).fetchall()
    return {row[0] for row in rows}


def count_jobs(conn: sqlite3.Connection, filter_status: str | None = None) -> int:
    """Return the number of jobs, optionally filtered by filter_status."""
    if filter_status is not None:
        row = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE filter_status = ?", (filter_status,)
        ).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()
    return row[0]
