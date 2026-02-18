"""Hitachi Energy career page scraper via Workday JSON API."""

from __future__ import annotations

import logging
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from job_scraper.scrapers.base import BaseScraper
from job_scraper.scrapers.career_pages.location import is_romandie, normalize_location

logger = logging.getLogger(__name__)

_API_BASE = "https://hitachi.wd1.myworkdayjobs.com/wday/cxs/hitachi/hitachi"
_JOBS_URL = f"{_API_BASE}/jobs"
_DETAIL_URL = _API_BASE  # + externalPath
_SWITZERLAND_FACET = "187134fccb084a0ea9b4b95f23890dbe"
_PAGE_SIZE = 20


class HitachiScraper(BaseScraper):
    """Scraper for Hitachi Energy's career page (Workday backend)."""

    def __init__(self) -> None:
        super().__init__("hitachi")

    # ------------------------------------------------------------------
    # Listing parsing
    # ------------------------------------------------------------------

    @staticmethod
    def parse_listing(data: dict) -> list[dict]:
        """Extract job postings from a Workday API response dict.

        Returns list of dicts with keys: title, externalPath, locationsText.
        """
        return data.get("jobPostings", [])

    @staticmethod
    def get_total_count(data: dict) -> int:
        """Extract total job count from a Workday API response."""
        return data.get("total", 0)

    # ------------------------------------------------------------------
    # Detail parsing
    # ------------------------------------------------------------------

    @staticmethod
    def parse_detail(data: dict) -> dict:
        """Parse a Workday job detail JSON response into a job dict."""
        info = data.get("jobPostingInfo", {})
        result: dict = {
            "title": info.get("title"),
            "company": "Hitachi Energy",
            "location": info.get("location"),
            "location_city": None,
            "location_canton": None,
            "description": None,
            "qualifications": None,
            "language_requirements": None,
            "experience_level": None,
            "deadline": None,
            "date_posted": info.get("startDate"),
        }

        # Location normalization
        raw_loc = info.get("location", "")
        if raw_loc:
            city, canton = normalize_location(raw_loc)
            result["location_city"] = city
            result["location_canton"] = canton

        # Parse HTML description
        raw_desc = info.get("jobDescription", "")
        if raw_desc:
            soup = BeautifulSoup(raw_desc, "html.parser")
            full_text = soup.get_text(separator="\n", strip=True)
            result["description"] = full_text

            # Try to split qualifications from description
            qual_match = re.search(
                r"(qualifications?\s+for\s+the\s+role|your\s+background|requirements?|your\s+profile)",
                full_text, re.I,
            )
            if qual_match:
                result["qualifications"] = full_text[qual_match.start():]
                result["description"] = full_text[:qual_match.start()]

            # Language requirements
            lang_patterns = re.findall(
                r"(?:english|french|german|deutsch|français|francais)"
                r"(?:\s*(?:and|required|fluent|native|mandatory|preferred|courant))*",
                full_text, re.I,
            )
            if lang_patterns:
                result["language_requirements"] = ", ".join(lang_patterns)

        return result

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    def parse(self, response: requests.Response) -> list[dict]:
        """Parse a Workday API listing response."""
        return self.parse_listing(response.json())

    def _fetch_listing(self, offset: int = 0, search_text: str = "") -> dict:
        """POST to the Workday jobs API and return the JSON response."""
        payload = {
            "appliedFacets": {
                "locationCountry": [_SWITZERLAND_FACET],
            },
            "limit": _PAGE_SIZE,
            "offset": offset,
            "searchText": search_text,
        }
        self.session.headers.update({"Content-Type": "application/json"})
        resp = self.session.post(_JOBS_URL, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _fetch_detail(self, external_path: str) -> dict:
        """GET a single job detail from the Workday API."""
        url = f"{_DETAIL_URL}{external_path}"
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def scrape(self) -> list[dict]:
        """Fetch all Swiss jobs from Workday API, parse details, filter to Romandie."""
        all_jobs: list[dict] = []
        offset = 0
        total = None  # capture from first response only

        while True:
            try:
                data = self._fetch_listing(offset=offset)
            except Exception as exc:
                logger.warning("Hitachi listing API failed at offset %d: %s", offset, exc)
                break

            postings = self.parse_listing(data)

            # Use total from first page (Workday sometimes returns 0 on later pages)
            if total is None:
                total = self.get_total_count(data)

            if not postings:
                break

            for posting in postings:
                ext_path = posting.get("externalPath", "")
                try:
                    detail_data = self._fetch_detail(ext_path)
                    job = self.parse_detail(detail_data)

                    # Skip non-Romandie
                    if job.get("location") and not is_romandie(job["location"]):
                        logger.debug("Skipping non-Romandie job: %s", job.get("title"))
                        continue

                    job["url"] = f"https://hitachi.wd1.myworkdayjobs.com/hitachi{ext_path}"
                    job["source"] = "hitachi"
                    job["date_scraped"] = datetime.utcnow().isoformat()
                    all_jobs.append(job)
                except Exception as exc:
                    logger.warning("Hitachi detail failed %s: %s", ext_path, exc)

            offset += _PAGE_SIZE
            if offset >= total:
                break

        logger.info("Hitachi scraper found %d jobs", len(all_jobs))
        return all_jobs
