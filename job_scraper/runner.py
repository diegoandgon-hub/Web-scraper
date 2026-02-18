"""F10.2 / F10.3 — Scraper runner with per-scraper isolation and run summary."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from job_scraper.scrapers.base import BaseScraper
from job_scraper.scrapers.exceptions import ParseError, ScrapingError

logger = logging.getLogger(__name__)


@dataclass
class RunSummary:
    """Counts for a single scrape run across all sources."""

    sources_succeeded: list[str] = field(default_factory=list)
    sources_failed: list[str] = field(default_factory=list)
    new_jobs: int = 0
    duplicates_skipped: int = 0
    collected_jobs: list[dict] = field(default_factory=list)

    def log(self) -> None:
        logger.info(
            "Run complete — succeeded: %s, failed: %s, new jobs: %d, duplicates: %d",
            ", ".join(self.sources_succeeded) or "(none)",
            ", ".join(self.sources_failed) or "(none)",
            self.new_jobs,
            self.duplicates_skipped,
        )


def run_scrapers(scrapers: list[BaseScraper]) -> RunSummary:
    """Run each scraper with per-scraper isolation.

    F10.2: A ``ScrapingError`` or ``ParseError`` in one scraper does not
    prevent others from running.  Within a single scraper, a ``ParseError``
    for one job does not block other jobs.

    Returns a :class:`RunSummary` with counts of successes, failures,
    new jobs, and duplicates.
    """
    summary = RunSummary()

    for scraper in scrapers:
        try:
            logger.info("Starting scraper: %s", scraper.source_name)
            jobs = scraper.scrape()
            summary.sources_succeeded.append(scraper.source_name)
            summary.new_jobs += len(jobs)
            summary.collected_jobs.extend(jobs)
            logger.info(
                "Scraper %s finished — %d jobs", scraper.source_name, len(jobs)
            )
        except (ScrapingError, ParseError) as exc:
            summary.sources_failed.append(scraper.source_name)
            logger.error(
                "Scraper %s failed: %s", scraper.source_name, exc
            )
        except Exception as exc:
            summary.sources_failed.append(scraper.source_name)
            logger.error(
                "Scraper %s unexpected error: %s", scraper.source_name, exc
            )

    summary.log()
    return summary
