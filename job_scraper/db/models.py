"""SQLite schema definition and database initialization for the jobs table."""

from __future__ import annotations

import sqlite3

from job_scraper.config import DATABASE_PATH

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    title                 TEXT    NOT NULL,
    company               TEXT    NOT NULL,
    location_city         TEXT,
    location_canton       TEXT,
    description           TEXT,
    qualifications        TEXT,
    language_requirements TEXT,
    experience_level      TEXT,
    deadline              TEXT,
    url                   TEXT    NOT NULL UNIQUE,
    date_posted           TEXT,
    date_scraped          TEXT    NOT NULL,
    source                TEXT    NOT NULL,
    filter_status         TEXT    DEFAULT 'unprocessed',
    filter_reason         TEXT,
    content_hash          TEXT
);
"""


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Return a connection to the SQLite database.

    Args:
        db_path: Path to the database file. Defaults to DATABASE_PATH from config.
                 Use \":memory:\" for in-memory databases (testing).
    """
    path = db_path if db_path is not None else DATABASE_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | None = None) -> sqlite3.Connection:
    """Create the jobs table idempotently and return the connection.

    Calling this function multiple times is safe — it uses CREATE TABLE IF NOT EXISTS.

    Args:
        db_path: Path to the database file. Defaults to DATABASE_PATH from config.
                 Use \":memory:\" for in-memory databases (testing).
    """
    conn = get_connection(db_path)
    conn.execute(SCHEMA_SQL)
    conn.commit()
    return conn
