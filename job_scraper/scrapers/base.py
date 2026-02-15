"""Abstract BaseScraper with retry logic, robots.txt compliance, and UA rotation."""

from __future__ import annotations

import random
import time
from abc import ABC, abstractmethod

import requests

from job_scraper.config import REQUEST_DELAY_SECONDS, USER_AGENTS
from job_scraper.robots import is_allowed
from job_scraper.scrapers.exceptions import ScrapingError

_MAX_RETRIES = 3
_TIMEOUT = 30


class BaseScraper(ABC):
    """Abstract base class for all scrapers.

    Subclasses must implement ``parse(response)`` and ``scrape()``.
    """

    def __init__(self, source_name: str) -> None:
        self.source_name = source_name
        self.session = requests.Session()
        self._rotate_user_agent()

    # ------------------------------------------------------------------
    # Session helpers
    # ------------------------------------------------------------------

    def _rotate_user_agent(self) -> None:
        """Set a random User-Agent header on the session."""
        ua = random.choice(USER_AGENTS)
        self.session.headers.update({"User-Agent": ua})

    # ------------------------------------------------------------------
    # Fetch with retries, robots check, delay, and UA rotation
    # ------------------------------------------------------------------

    def fetch(self, url: str) -> requests.Response:
        """Fetch *url* respecting robots.txt, delay, retries, and UA rotation.

        Raises:
            ScrapingError: after ``_MAX_RETRIES`` consecutive 429/5xx responses,
                           or if robots.txt disallows the URL.
        """
        if not is_allowed(url):
            raise ScrapingError(f"robots.txt disallows: {url}")

        self._rotate_user_agent()
        time.sleep(REQUEST_DELAY_SECONDS)

        for attempt in range(1, _MAX_RETRIES + 1):
            response = self.session.get(url, timeout=_TIMEOUT)

            if response.status_code < 400:
                return response

            if response.status_code == 429 or response.status_code >= 500:
                if attempt == _MAX_RETRIES:
                    raise ScrapingError(
                        f"{url} returned {response.status_code} after "
                        f"{_MAX_RETRIES} retries"
                    )
                backoff = 2 ** attempt
                time.sleep(backoff)
                continue

            # 4xx (other than 429) — no point retrying
            raise ScrapingError(
                f"{url} returned {response.status_code}"
            )

        # Should not be reached, but satisfies type checkers
        raise ScrapingError(f"{url} failed after {_MAX_RETRIES} retries")  # pragma: no cover

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def parse(self, response: requests.Response) -> list[dict]:
        """Parse a fetched response into a list of job dicts."""

    @abstractmethod
    def scrape(self) -> list[dict]:
        """Run the full scrape pipeline: fetch pages, parse, return jobs."""
