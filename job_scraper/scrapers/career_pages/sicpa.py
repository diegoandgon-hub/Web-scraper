"""F5.SICPA.1-3 — SICPA career page scraper (Taleo at jobs.sicpa.com)."""

from __future__ import annotations

import logging
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from job_scraper.scrapers.base import BaseScraper
from job_scraper.scrapers.career_pages.location import is_romandie, normalize_location

logger = logging.getLogger(__name__)

_BASE_URL = "https://jobs.sicpa.com"
_LISTING_URL = f"{_BASE_URL}/go/Jobs/4233501/"
_LISTING_PARAMS = "q=&sortColumn=referencedate&sortDirection=desc"
_PAGE_SIZE = 20


class SICPAScraper(BaseScraper):
    """Scraper for SICPA's career page (Taleo)."""

    def __init__(self) -> None:
        super().__init__("sicpa")

    # ------------------------------------------------------------------
    # F5.SICPA.1 — Listing page parsing + pagination
    # ------------------------------------------------------------------

    @staticmethod
    def parse_listing(html: str) -> list[dict]:
        """Extract job rows from the Taleo listing table.

        Returns list of dicts with: title, url, department, location, date_posted.
        """
        soup = BeautifulSoup(html, "lxml")
        jobs: list[dict] = []
        for tr in soup.select("tr.data-row"):
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            title_a = tr.select_one("a[href*='/job/']")
            if not title_a:
                continue
            href = title_a.get("href", "")
            if href and not href.startswith("http"):
                href = _BASE_URL + href
            jobs.append({
                "title": title_a.get_text(strip=True),
                "url": href,
                "department": tds[1].get_text(strip=True) if len(tds) > 1 else None,
                "location": tds[2].get_text(strip=True) if len(tds) > 2 else None,
                "date_posted": tds[3].get_text(strip=True) if len(tds) > 3 else None,
            })
        return jobs

    @staticmethod
    def get_total_count(html: str) -> int:
        """Extract the total job count from the pagination label."""
        soup = BeautifulSoup(html, "lxml")
        pag = soup.select_one(".paginationLabel")
        if pag:
            match = re.search(r"of\s*(\d+)", pag.get_text())
            if match:
                return int(match.group(1))
        # Fallback: search anywhere
        count_el = soup.find(string=re.compile(r"of\s+\d+"))
        if count_el:
            match = re.search(r"of\s+(\d+)", count_el)
            if match:
                return int(match.group(1))
        return 0

    # ------------------------------------------------------------------
    # F5.SICPA.2 — Job detail parsing
    # ------------------------------------------------------------------

    @staticmethod
    def parse_detail(html: str) -> dict:
        """Parse a SICPA/Taleo job detail page into a job dict."""
        soup = BeautifulSoup(html, "lxml")
        result: dict = {
            "title": None,
            "company": "SICPA",
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
        h1 = soup.find("h1")
        if h1:
            result["title"] = h1.get_text(strip=True)

        # Location — Taleo uses span.jobGeoLocation
        loc_el = soup.select_one("span.jobGeoLocation")
        if not loc_el:
            loc_el = soup.select_one("span.rtltextaligneligible")
        if loc_el:
            raw_loc = loc_el.get_text(strip=True)
            result["location"] = raw_loc
            city, canton = normalize_location(raw_loc)
            result["location_city"] = city
            result["location_canton"] = canton

        # Posted date — look for "Posted on:" label
        posted_el = soup.find(string=re.compile(r"Posted on:", re.I))
        if posted_el:
            parent = posted_el.find_parent()
            if parent:
                text = parent.get_text(strip=True)
                match = re.search(r"(\d{1,2}\s+\w+\s+\d{4})", text)
                if match:
                    result["date_posted"] = match.group(1)

        # Description — Taleo uses span.jobdescription
        desc_el = soup.select_one("span.jobdescription")
        if not desc_el:
            desc_el = soup.select_one(".job-description")
        if not desc_el:
            # Fallback: find the narrowest div containing "Long Description"
            desc_el = soup.select_one("div.displayDTM")

        if desc_el:
            full_text = desc_el.get_text(separator="\n", strip=True)

            # Strip the "Long Description" label if present
            full_text = re.sub(r"^.*?Long Description\s*", "", full_text, count=1)

            result["description"] = full_text

            # Try to find qualifications section
            qual_match = re.search(
                r"(qualifications?|requirements?|your\s+profile|what\s+we\s+expect)",
                full_text, re.I,
            )
            if qual_match:
                result["qualifications"] = full_text[qual_match.start():]

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
        return self.parse_listing(response.text)

    def scrape(self) -> list[dict]:
        """Fetch listing pages, then detail pages. Keep only Switzerland jobs."""
        all_jobs: list[dict] = []
        start_row = 0

        while True:
            url = f"{_LISTING_URL}?{_LISTING_PARAMS}&startrow={start_row}"
            try:
                resp = self.fetch(url)
            except Exception as exc:
                logger.warning("SICPA listing page failed at row %d: %s", start_row, exc)
                break

            listings = self.parse_listing(resp.text)
            if not listings:
                break

            # Filter to Switzerland locations before fetching details
            swiss_listings = [
                j for j in listings
                if j.get("location") and "Switzerland" in j["location"]
            ]

            for listing in swiss_listings:
                job_url = listing["url"]
                try:
                    detail_resp = self.fetch(job_url)
                    job = self.parse_detail(detail_resp.text)

                    # Use listing data as fallback
                    job["title"] = job["title"] or listing["title"]
                    job["date_posted"] = job["date_posted"] or listing.get("date_posted")

                    # F5.SICPA.3 — skip non-Romandie
                    if job.get("location") and not is_romandie(job["location"]):
                        logger.debug("Skipping non-Romandie job: %s", job.get("title"))
                        continue

                    job["url"] = job_url
                    job["source"] = "sicpa"
                    job["date_scraped"] = datetime.utcnow().isoformat()
                    all_jobs.append(job)
                except Exception as exc:
                    logger.warning("SICPA detail page failed %s: %s", job_url, exc)

            total = self.get_total_count(resp.text)
            start_row += _PAGE_SIZE
            if start_row >= total or total == 0:
                break

        logger.info("SICPA scraper found %d jobs", len(all_jobs))
        return all_jobs
