"""F5.Alpiq.1-3 — Alpiq career page scraper (alpiq.com/career/open-jobs)."""

from __future__ import annotations

import logging
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from job_scraper.scrapers.base import BaseScraper
from job_scraper.scrapers.career_pages.location import is_romandie, normalize_location

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.alpiq.com"
_LISTING_URL = f"{_BASE_URL}/career/open-jobs"
# Pagination pattern: /career/open-jobs/jobs/job-page-N/f1-*/f2-*/search
_PAGE_URL_TEMPLATE = _BASE_URL + "/career/open-jobs/jobs/job-page-{page}/f1-%2A/f2-%2A/search"


class AlpiqScraper(BaseScraper):
    """Scraper for Alpiq's career page (SuccessFactors-powered)."""

    def __init__(self) -> None:
        super().__init__("alpiq")

    # ------------------------------------------------------------------
    # F5.Alpiq.1 — Listing page parsing + pagination
    # ------------------------------------------------------------------

    @staticmethod
    def parse_listing(html: str) -> list[dict]:
        """Extract job items from the Alpiq listing page.

        Returns list of dicts with: title, url, department, location, description_snippet.
        """
        soup = BeautifulSoup(html, "lxml")
        jobs: list[dict] = []
        for card in soup.select("ul.job-item"):
            title_a = card.select_one("a.title")
            if not title_a:
                continue
            href = title_a.get("href", "")
            if href and not href.startswith("http"):
                href = _BASE_URL + href

            # Department tag
            tag_el = card.select_one("div.tag span")
            department = tag_el.get_text(strip=True) if tag_el else None

            # Description snippet
            desc_el = card.select_one("p.description")
            snippet = desc_el.get_text(strip=True) if desc_el else None

            # Contract/location: "City - 80-100%" and "Permanent"
            contract_el = card.select_one("div.contract")
            location = None
            if contract_el:
                spans = contract_el.find_all("span")
                if spans:
                    # First span is typically "City - percentage"
                    location = spans[0].get_text(strip=True)

            jobs.append({
                "title": title_a.get_text(strip=True),
                "url": href,
                "department": department,
                "location_raw": location,
                "description_snippet": snippet,
            })
        return jobs

    @staticmethod
    def get_total_count(html: str) -> int:
        """Extract total page count from pagination links."""
        soup = BeautifulSoup(html, "lxml")
        # Find the last page number from pagination links
        page_links = soup.select("a[href*='job-page-']")
        max_page = 1
        for link in page_links:
            match = re.search(r"job-page-(\d+)", link.get("href", ""))
            if match:
                max_page = max(max_page, int(match.group(1)))
        return max_page

    # ------------------------------------------------------------------
    # F5.Alpiq.2 — Job detail parsing
    # ------------------------------------------------------------------

    @staticmethod
    def parse_detail(html: str) -> dict:
        """Parse an Alpiq job detail page into a job dict."""
        soup = BeautifulSoup(html, "lxml")
        result: dict = {
            "title": None,
            "company": "Alpiq",
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

        # Location — from the SuccessFactors detail frame
        # Pattern: "City - 100% | Permanent"
        frame = soup.select_one(".frame-type-successfactors_jobdetail")
        if frame:
            # Look for location paragraph (first <p> after tag/title)
            for p in frame.find_all("p"):
                text = p.get_text(strip=True)
                if re.match(r"^[\w\s/]+ - \d+", text):
                    # Extract city from "City - 100% | Permanent"
                    city_match = re.match(r"^([\w\s/]+?)\s*-\s*\d+", text)
                    if city_match:
                        raw_city = city_match.group(1).strip()
                        result["location"] = raw_city
                        city, canton = normalize_location(raw_city)
                        result["location_city"] = city
                        result["location_canton"] = canton
                    break

        # Description — full text from the detail frame
        if frame:
            full_text = frame.get_text(separator="\n", strip=True)
            # Remove the title and location line from the beginning
            lines = full_text.split("\n")
            # Skip header lines (tag, title, location)
            desc_start = 0
            for i, line in enumerate(lines):
                if len(line) > 50:  # First substantial paragraph
                    desc_start = i
                    break
            result["description"] = "\n".join(lines[desc_start:])

            # Qualifications
            qual_match = re.search(
                r"(qualifications?|requirements?|your\s+profile|what\s+we\s+expect|what\s+you\s+bring)",
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
        """Fetch listing pages, then detail pages. Skip non-Romandie jobs."""
        all_jobs: list[dict] = []

        # Fetch first page to get total page count
        try:
            resp = self.fetch(_LISTING_URL)
        except Exception as exc:
            logger.warning("Alpiq listing page 1 failed: %s", exc)
            logger.info("Alpiq scraper found 0 jobs")
            return all_jobs

        total_pages = self.get_total_count(resp.text)
        pages_html = [resp.text]

        # Fetch remaining pages
        for page in range(2, total_pages + 1):
            try:
                resp = self.fetch(_PAGE_URL_TEMPLATE.format(page=page))
                pages_html.append(resp.text)
            except Exception as exc:
                logger.warning("Alpiq listing page %d failed: %s", page, exc)

        # Parse all listing pages
        all_listings: list[dict] = []
        seen_urls: set[str] = set()
        for html in pages_html:
            for listing in self.parse_listing(html):
                url = listing["url"]
                if url not in seen_urls:
                    seen_urls.add(url)
                    all_listings.append(listing)

        # Fetch and parse detail pages
        for listing in all_listings:
            job_url = listing["url"]
            try:
                detail_resp = self.fetch(job_url)
                job = self.parse_detail(detail_resp.text)

                # Use listing data as fallback
                job["title"] = job["title"] or listing["title"]

                # F5.Alpiq.3 — skip non-Romandie
                loc = job.get("location") or listing.get("location_raw", "")
                if loc and not is_romandie(loc):
                    logger.debug("Skipping non-Romandie job: %s", job.get("title"))
                    continue

                # If we still don't have location from detail, parse from listing
                if not job.get("location_city") and listing.get("location_raw"):
                    raw = listing["location_raw"]
                    city_part = re.match(r"^([\w\s/]+?)(?:\s*-\s*\d+)?$", raw)
                    if city_part:
                        city, canton = normalize_location(city_part.group(1).strip())
                        job["location_city"] = city
                        job["location_canton"] = canton
                        job["location"] = city_part.group(1).strip()

                job["url"] = job_url
                job["source"] = "alpiq"
                job["date_scraped"] = datetime.utcnow().isoformat()
                all_jobs.append(job)
            except Exception as exc:
                logger.warning("Alpiq detail page failed %s: %s", job_url, exc)

        logger.info("Alpiq scraper found %d jobs", len(all_jobs))
        return all_jobs
