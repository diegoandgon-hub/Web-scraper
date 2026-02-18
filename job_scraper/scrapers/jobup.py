"""JobUp.ch scraper — replaces LinkedIn (blocked by robots.txt).

JobUp.ch is the main French-speaking Swiss job board. Job listing data is
embedded in the HTML as a ``__INIT__`` JavaScript variable containing JSON.
Detail pages include JSON-LD ``JobPosting`` schema.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from job_scraper.config import ROMANDIE_CITIES, TARGET_KEYWORDS
from job_scraper.scrapers.base import BaseScraper
from job_scraper.scrapers.career_pages.location import normalize_location

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.jobup.ch"
_SEARCH_URL = f"{_BASE_URL}/en/jobs/"
_DETAIL_URL = f"{_BASE_URL}/en/jobs/detail/"
_ROWS_PER_PAGE = 20


# ------------------------------------------------------------------
# URL generation
# ------------------------------------------------------------------

def build_search_urls() -> list[str]:
    """Generate search URLs for all (keyword x city) combinations.

    Returns a deduplicated list of URLs.
    """
    urls: list[str] = []
    seen: set[tuple[str, str]] = set()

    for keywords in TARGET_KEYWORDS.values():
        for keyword in keywords:
            for city in ROMANDIE_CITIES:
                key = (keyword.lower(), city.lower())
                if key in seen:
                    continue
                seen.add(key)
                url = (
                    f"{_SEARCH_URL}?term={quote_plus(keyword)}"
                    f"&location={quote_plus(city)}&rows={_ROWS_PER_PAGE}"
                )
                urls.append(url)

    return urls


# ------------------------------------------------------------------
# Parsing helpers
# ------------------------------------------------------------------

def _extract_init_json(html: str) -> dict | None:
    """Extract the __INIT__ JSON object from the HTML page.

    Uses brace-counting to handle the large nested JSON reliably.
    """
    match = re.search(r"__INIT__\s*=\s*", html)
    if not match:
        return None

    start = match.end()
    if start >= len(html) or html[start] != "{":
        return None

    depth = 0
    for i in range(start, len(html)):
        if html[i] == "{":
            depth += 1
        elif html[i] == "}":
            depth -= 1
        if depth == 0:
            try:
                return json.loads(html[start : i + 1])
            except (json.JSONDecodeError, ValueError):
                logger.warning("Failed to parse __INIT__ JSON from page")
                return None

    return None


def parse_listing(html: str) -> list[dict]:
    """Parse a search results page and return job summary dicts.

    Each dict contains: id, title, company, place, publicationDate, url.
    """
    data = _extract_init_json(html)
    if not data:
        return []

    try:
        results = data["vacancy"]["results"]["main"]["results"]
    except (KeyError, TypeError):
        return []

    jobs = []
    for item in results:
        job_id = item.get("id", "")
        jobs.append({
            "id": job_id,
            "title": item.get("title"),
            "company": (item.get("company") or {}).get("name"),
            "place": item.get("place"),
            "publicationDate": item.get("publicationDate"),
            "url": f"{_DETAIL_URL}{job_id}/",
        })

    return jobs


def get_total_pages(html: str) -> int:
    """Extract the total number of result pages from a listing page."""
    data = _extract_init_json(html)
    if not data:
        return 1

    try:
        return data["vacancy"]["results"]["main"]["meta"]["numPages"]
    except (KeyError, TypeError):
        return 1


def parse_detail(html: str) -> dict:
    """Parse a job detail page and return a full job dict.

    Extracts data from the JSON-LD ``JobPosting`` schema embedded in the page.
    """
    result: dict = {
        "title": None,
        "company": None,
        "description": None,
        "qualifications": None,
        "location": None,
        "location_city": None,
        "location_canton": None,
        "date_posted": None,
        "language_requirements": None,
        "experience_level": None,
        "url": None,
    }

    soup = BeautifulSoup(html, "html.parser")

    # Extract JSON-LD JobPosting (may be standalone dict or inside an array)
    job_data = None
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            ld = json.loads(script.string or "")
            candidates = ld if isinstance(ld, list) else [ld]
            for item in candidates:
                if isinstance(item, dict) and item.get("@type") == "JobPosting":
                    job_data = item
                    break
            if job_data:
                break
        except (json.JSONDecodeError, ValueError):
            continue

    if not job_data:
        # Fallback: try __INIT__ JSON for the title at minimum
        title_el = soup.find("h1")
        if title_el:
            result["title"] = title_el.get_text(strip=True)
        return result

    result["title"] = job_data.get("title")

    # Company
    org = job_data.get("hiringOrganization")
    if isinstance(org, dict):
        result["company"] = org.get("name")

    # Date posted
    date_str = job_data.get("datePosted", "")
    if date_str:
        try:
            dt = datetime.fromisoformat(date_str)
            result["date_posted"] = dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            result["date_posted"] = date_str[:10] if len(date_str) >= 10 else date_str

    # Location
    loc = job_data.get("jobLocation")
    if isinstance(loc, dict):
        address = loc.get("address") or {}
        city = address.get("addressLocality", "")
        country = address.get("addressCountry", "")
        postal_code = address.get("postalCode", "")
        raw_location = f"{city}, {country}" if city else ""
        result["location"] = raw_location

        norm_city, norm_canton = normalize_location(raw_location, postal_code=postal_code)
        result["location_city"] = norm_city
        result["location_canton"] = norm_canton

    # Description — HTML content, extract text
    desc_html = job_data.get("description", "")
    if desc_html:
        desc_soup = BeautifulSoup(desc_html, "html.parser")
        result["description"] = desc_soup.get_text(separator="\n", strip=True)

    # Extract qualifications and language from description text
    desc_text = result["description"] or ""

    # Qualifications — look for requirements/qualifications sections
    qual_match = re.search(
        r"(?:qualifications?|requirements?|profile|your profile)[\s:]*\n((?:.*\n?){1,10})",
        desc_text,
        re.IGNORECASE,
    )
    if qual_match:
        result["qualifications"] = qual_match.group(1).strip()

    # Language requirements
    lang_match = re.findall(
        r"\b(English|French|German|Français|Anglais|Allemand)\b",
        desc_text,
        re.IGNORECASE,
    )
    if lang_match:
        result["language_requirements"] = ", ".join(sorted(set(lang_match)))

    # Experience level
    exp_match = re.search(
        r"(entry[- ]level|junior|graduate|senior|[0-9]+[- ]?[0-9]*\s*years?)",
        desc_text,
        re.IGNORECASE,
    )
    if exp_match:
        result["experience_level"] = exp_match.group(1)

    # Employment type
    emp_type = job_data.get("employmentType")
    if emp_type:
        if isinstance(emp_type, list):
            result["employment_type"] = ", ".join(emp_type)
        else:
            result["employment_type"] = str(emp_type)

    return result


# ------------------------------------------------------------------
# Scraper class
# ------------------------------------------------------------------

class JobUpScraper(BaseScraper):
    """Scraper for jobup.ch — French-speaking Swiss job board."""

    def __init__(self) -> None:
        super().__init__("jobup")

    def parse(self, response: requests.Response) -> list[dict]:
        """Parse a listing page response."""
        return parse_listing(response.text)

    def scrape(self) -> list[dict]:
        """Scrape all keyword x city search URLs, paginate, fetch details.

        Deduplicates by job ID across queries. Filters to Romandie locations.
        """
        search_urls = build_search_urls()
        all_jobs: list[dict] = []
        seen_ids: set[str] = set()

        for search_url in search_urls:
            page = 1
            while True:
                page_url = f"{search_url}&page={page}" if page > 1 else search_url
                try:
                    response = self.fetch(page_url)
                except Exception as exc:
                    logger.warning("JobUp search failed %s: %s", page_url, exc)
                    break

                listings = parse_listing(response.text)
                if not listings:
                    break

                total_pages = get_total_pages(response.text) if page == 1 else total_pages

                for listing in listings:
                    job_id = listing.get("id", "")
                    if job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)

                    # Fetch detail page
                    detail_url = listing["url"]
                    try:
                        detail_resp = self.fetch(detail_url)
                        job = parse_detail(detail_resp.text)
                    except Exception as exc:
                        logger.warning("JobUp detail failed %s: %s", detail_url, exc)
                        continue

                    job["url"] = detail_url
                    job["source"] = "jobup"
                    job["date_scraped"] = datetime.utcnow().isoformat()
                    all_jobs.append(job)

                if page >= total_pages:
                    break
                page += 1

        logger.info("JobUp scraper found %d unique jobs", len(all_jobs))
        return all_jobs
