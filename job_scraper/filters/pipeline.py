"""F6.4 — Filter pipeline: keyword filter → LLM fallback for ambiguous jobs."""

from __future__ import annotations

import logging

from job_scraper.db.crud import get_jobs, update_filter_status
from job_scraper.filters.keyword_filter import keyword_filter
from job_scraper.filters.llm_filter import llm_filter

logger = logging.getLogger(__name__)


def run_filters(conn, use_llm: bool = False) -> dict[str, int]:
    """Process all unprocessed jobs through keyword filter, then optionally LLM.

    Args:
        conn: SQLite database connection.
        use_llm: If True, send ambiguous jobs to the LLM filter.

    Returns:
        Summary dict: {"passed": N, "rejected": N, "ambiguous": N}
    """
    summary = {"passed": 0, "rejected": 0, "ambiguous": 0}

    jobs = get_jobs(conn, filter_status="unprocessed")
    logger.info("Filtering %d unprocessed jobs", len(jobs))

    for job in jobs:
        status, reason = keyword_filter(job)
        update_filter_status(conn, job["id"], status, reason)

        if status == "ambiguous" and use_llm:
            llm_status, llm_reason = llm_filter(job)
            update_filter_status(conn, job["id"], llm_status, llm_reason)
            status = llm_status

        summary[status] = summary.get(status, 0) + 1

    logger.info(
        "Filter complete — passed: %d, rejected: %d, ambiguous: %d",
        summary["passed"],
        summary["rejected"],
        summary["ambiguous"],
    )
    return summary
