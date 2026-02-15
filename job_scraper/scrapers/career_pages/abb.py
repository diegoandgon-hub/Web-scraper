"""F5.ABB.1-3 — ABB career page scraper."""

from __future__ import annotations

import logging
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from job_scraper.scrapers.base import BaseScraper
from job_scraper.scrapers.career_pages.location import is_romandie, normalize_location

logger = logging.getLogger(__name__)

_LISTING_URL = "https://careers.abb/global/en/search-results"
_LISTING_PARAMS = {
    "keywords": "",
    "from": "0",
    "s": "1",
}
_PAGE_SIZE = 25


class ABBScraper(BaseScraper):
    """Scraper for ABB's career page."""

    def __init__(self) -> None:
        super().__init__("abb")

    # ------------------------------------------------------------------
    # F5.ABB.1 — Listing page parsing + pagination
    # ------------------------------------------------------------------

    @staticmethod
    def parse_listing(html: str) -> list[str]:
        """Extract job detail URLs from a listing page."""
        soup = BeautifulSoup(html, "lxml")
        urls: list[str] = []
        for link in soup.select("a[href*='/job/']"):
            href = link.get("href", "")
            if href and href not in urls:
                urls.append(href)
        return urls

    @staticmethod
    def get_total_count(html: str) -> int:
        """Extract the total job count from a listing page."""
        soup = BeautifulSoup(html, "lxml")
        count_el = soup.find(string=re.compile(r"\d+\s*(?:results?|jobs?)", re.I))
        if count_el:
            match = re.search(r"(\d+)", count_el)
            if match:
                return int(match.group(1))
        return 0

    # ------------------------------------------------------------------
    # F5.ABB.2 — Job detail parsing
    # ------------------------------------------------------------------

    @staticmethod
    def parse_detail(html: str) -> dict:
        """Parse an ABB job detail page into a job dict."""
        soup = BeautifulSoup(html, "lxml")
        result: dict = {
            "title": None,
            "company": "ABB",
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

        # Title
        title_el = soup.find("h1") or soup.find("title")
        if title_el:
            result["title"] = title_el.get_text(strip=True)

        # Location
        loc_el = (
            soup.find("span", class_=re.compile(r"location", re.I))
            or soup.find("div", class_=re.compile(r"location", re.I))
        )
        if loc_el:
            raw_loc = loc_el.get_text(strip=True)
            result["location"] = raw_loc
            city, canton = normalize_location(raw_loc)
            result["location_city"] = city
            result["location_canton"] = canton

        # Description
        desc_el = soup.find("div", class_=re.compile(r"description|job-details", re.I))
        if desc_el:
            result["description"] = desc_el.get_text(separator="\n", strip=True)

        # Qualifications
        qual_el = soup.find(
            "div", class_=re.compile(r"qualifications|requirements", re.I)
        )
        if qual_el:
            result["qualifications"] = qual_el.get_text(separator="\n", strip=True)

        # Date posted
        date_el = soup.find(string=re.compile(r"posted|date", re.I))
        if date_el:
            parent = date_el.find_parent()
            if parent:
                match = re.search(r"(\d{4}-\d{2}-\d{2})", parent.get_text())
                if match:
                    result["date_posted"] = match.group(1)

        return result

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    def parse(self, response: requests.Response) -> list[dict]:
        """Parse a listing page response into job URLs."""
        return self.parse_listing(response.text)

    def scrape(self) -> list[dict]:
        """Fetch listing pages, then detail pages. Skip non-Romandie jobs."""
        all_jobs: list[dict] = []
        offset = 0

        while True:
            params = {**_LISTING_PARAMS, "from": str(offset)}
            try:
                resp = self.fetch(
                    f"{_LISTING_URL}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
                )
            except Exception as exc:
                logger.warning("ABB listing page failed at offset %d: %s", offset, exc)
                break

            job_urls = self.parse_listing(resp.text)
            if not job_urls:
                break

            for job_url in job_urls:
                try:
                    detail_resp = self.fetch(job_url)
                    job = self.parse_detail(detail_resp.text)

                    # F5.ABB.3 — skip non-Romandie
                    if job.get("location") and not is_romandie(job["location"]):
                        logger.debug("Skipping non-Romandie job: %s", job.get("title"))
                        continue

                    job["url"] = job_url
                    job["source"] = "abb"
                    job["date_scraped"] = datetime.utcnow().isoformat()
                    all_jobs.append(job)
                except Exception as exc:
                    logger.warning("ABB detail page failed %s: %s", job_url, exc)

            total = self.get_total_count(resp.text)
            offset += _PAGE_SIZE
            if offset >= total or total == 0:
                break

        logger.info("ABB scraper found %d jobs", len(all_jobs))
        return all_jobs
