"""Duplicate detection via content hashing and URL checks."""

from __future__ import annotations

import hashlib
import logging
import re
import string

from job_scraper.db.crud import get_all_content_hashes, insert_job, job_exists

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# F9.1 — Content hash: SHA-256 of normalized title+company+description
# ------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lowercase, strip whitespace, remove punctuation."""
    text = text.lower().strip()
    text = text.translate(str.maketrans("", "", string.punctuation))
    text = re.sub(r"\s+", " ", text)
    return text


def compute_content_hash(title: str, company: str, description: str) -> str:
    """Return SHA-256 hex digest of normalized title + company + description[:500]."""
    combined = (
        _normalize(title)
        + _normalize(company)
        + _normalize(description[:500])
    )
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------
# F9.4 — Integration: URL check (fast) -> content hash check -> insert
# ------------------------------------------------------------------

def is_duplicate(content_hash: str, existing_hashes: set[str]) -> bool:
    """Return True if *content_hash* is already in *existing_hashes*."""
    return content_hash in existing_hashes


def deduplicated_insert(conn, job_dict: dict, existing_hashes: set[str]) -> int | None:
    """Try to insert a job, skipping duplicates.

    1. URL dedup (F9.2): ``job_exists()`` — fast DB lookup.
    2. Content-hash dedup (F9.3): catches cross-source duplicates
       (same content, different URLs).
    3. DB insert with UNIQUE constraint as final safety net.

    Returns the new row id, or ``None`` if the job was a duplicate.
    """
    url = job_dict.get("url", "")

    # Step 1 — URL dedup (fast)
    if job_exists(conn, url):
        logger.debug("URL duplicate skipped: %s", url)
        return None

    # Step 2 — Content-hash dedup (cross-source)
    content_hash = job_dict.get("content_hash")
    if content_hash and is_duplicate(content_hash, existing_hashes):
        logger.debug("Content-hash duplicate skipped: %s", url)
        return None

    # Step 3 — Insert (UNIQUE constraint is the final safety net)
    job_id = insert_job(conn, job_dict)
    if job_id is None:
        logger.debug("DB-level duplicate skipped: %s", url)
        return None

    # Track the new hash so subsequent calls in the same batch catch it
    if content_hash:
        existing_hashes.add(content_hash)

    return job_id
