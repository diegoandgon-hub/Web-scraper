"""CERN career page scraper via SmartRecruiters public JSON API."""

from __future__ import annotations

import logging
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from job_scraper.scrapers.base import BaseScraper
from job_scraper.scrapers.career_pages.location import is_romandie, normalize_location

logger = logging.getLogger(__name__)

_API_BASE = "https://api.smartrecruiters.com/v1/companies/CERN/postings"
_PAGE_SIZE = 100


class CERNScraper(BaseScraper):
    """Scraper for CERN's career page (SmartRecruiters backend)."""

    def __init__(self) -> None:
        super().__init__("cern")

    # ------------------------------------------------------------------
    # Listing parsing
    # ------------------------------------------------------------------

    @staticmethod
    def parse_listing(data: dict) -> list[dict]:
        """Extract job summaries from a SmartRecruiters listing response.

        Returns list of dicts with keys: id, name, location, experienceLevel,
        department, releasedDate, ref.
        """
        return data.get("content", [])

    @staticmethod
    def get_total_count(data: dict) -> int:
        """Extract total job count from a SmartRecruiters response."""
        return data.get("totalFound", 0)

    # ------------------------------------------------------------------
    # Detail parsing
    # ------------------------------------------------------------------

    @staticmethod
    def parse_detail(data: dict) -> dict:
        """Parse a SmartRecruiters job detail JSON into a job dict."""
        result: dict = {
            "title": data.get("name"),
            "company": "CERN",
            "location": None,
            "location_city": None,
            "location_canton": None,
            "description": None,
            "qualifications": None,
            "language_requirements": None,
            "experience_level": None,
            "deadline": None,
            "date_posted": None,
        }

        # Location
        loc = data.get("location", {})
        raw_loc = loc.get("city", "")
        if raw_loc:
            result["location"] = f"{raw_loc}, Switzerland"
            city, canton = normalize_location(raw_loc)
            result["location_city"] = city
            result["location_canton"] = canton

        # Experience level
        exp = data.get("experienceLevel", {})
        if exp:
            result["experience_level"] = exp.get("label")

        # Date posted
        released = data.get("releasedDate", "")
        if released:
            try:
                dt = datetime.fromisoformat(released.replace("Z", "+00:00"))
                result["date_posted"] = dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                result["date_posted"] = released[:10] if len(released) >= 10 else released

        # Job description from jobAd sections
        sections = (data.get("jobAd") or {}).get("sections", {})

        desc_html = (sections.get("jobDescription") or {}).get("text", "")
        qual_html = (sections.get("qualifications") or {}).get("text", "")
        addl_html = (sections.get("additionalInformation") or {}).get("text", "")

        if desc_html:
            soup = BeautifulSoup(desc_html, "html.parser")
            result["description"] = soup.get_text(separator="\n", strip=True)

        if qual_html:
            soup = BeautifulSoup(qual_html, "html.parser")
            result["qualifications"] = soup.get_text(separator="\n", strip=True)
        elif result["description"]:
            # Try to split qualifications from description
            qual_match = re.search(
                r"(qualifications?|requirements?|your\s+profile|your\s+skills)",
                result["description"], re.I,
            )
            if qual_match:
                result["qualifications"] = result["description"][qual_match.start():]

        # Combine description text for language extraction
        full_text = "\n".join(filter(None, [
            result["description"], result.get("qualifications", ""),
            BeautifulSoup(addl_html, "html.parser").get_text(separator="\n", strip=True) if addl_html else "",
        ]))

        # Language requirements
        if full_text:
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
        """Parse a SmartRecruiters listing response."""
        return self.parse_listing(response.json())

    def _fetch_listing(self, offset: int = 0) -> dict:
        """GET the SmartRecruiters postings API with pagination."""
        url = f"{_API_BASE}?limit={_PAGE_SIZE}&offset={offset}"
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _fetch_detail(self, posting_id: str) -> dict:
        """GET a single job detail from the SmartRecruiters API."""
        url = f"{_API_BASE}/{posting_id}"
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def scrape(self) -> list[dict]:
        """Fetch all CERN jobs, parse details, filter to Romandie."""
        all_jobs: list[dict] = []
        offset = 0
        total = None

        while True:
            try:
                data = self._fetch_listing(offset=offset)
            except Exception as exc:
                logger.warning("CERN listing API failed at offset %d: %s", offset, exc)
                break

            postings = self.parse_listing(data)

            if total is None:
                total = self.get_total_count(data)

            if not postings:
                break

            for posting in postings:
                posting_id = posting.get("id", "")
                try:
                    detail_data = self._fetch_detail(posting_id)
                    job = self.parse_detail(detail_data)

                    # Skip non-Romandie
                    if job.get("location") and not is_romandie(job["location"]):
                        logger.debug("Skipping non-Romandie job: %s", job.get("title"))
                        continue

                    job["url"] = f"https://careers.cern/jobs/{posting_id}/"
                    job["source"] = "cern"
                    job["date_scraped"] = datetime.utcnow().isoformat()
                    all_jobs.append(job)
                except Exception as exc:
                    logger.warning("CERN detail failed %s: %s", posting_id, exc)

            offset += _PAGE_SIZE
            if offset >= total:
                break

        logger.info("CERN scraper found %d jobs", len(all_jobs))
        return all_jobs
