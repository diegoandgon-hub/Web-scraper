"""F4.1-F4.3 — LinkedIn public scraper: RSS feeds + job page parser."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from urllib.parse import quote_plus

import feedparser
import requests
from bs4 import BeautifulSoup

from job_scraper.config import ROMANDIE_CITIES, TARGET_KEYWORDS
from job_scraper.scrapers.base import BaseScraper
from job_scraper.scrapers.exceptions import ParseError

logger = logging.getLogger(__name__)

# LinkedIn RSS feed base URL
_RSS_BASE = "https://www.linkedin.com/jobs/search/feed"

# Signals that LinkedIn is showing a login wall instead of job content
_LOGIN_WALL_MARKERS = [
    "authwall",
    "sign in",
    "join now",
    "Log in or sign up",
]


# ------------------------------------------------------------------
# F4.3 — Query URL generation
# ------------------------------------------------------------------

def build_query_urls() -> list[str]:
    """Build one RSS feed URL per (keyword x city) combination.

    Returns a deduplicated list of feed URLs.
    """
    urls: list[str] = []
    seen: set[str] = set()

    for group_keywords in TARGET_KEYWORDS.values():
        for keyword in group_keywords:
            for city in ROMANDIE_CITIES:
                encoded_kw = quote_plus(keyword)
                encoded_city = quote_plus(city)
                url = f"{_RSS_BASE}?keywords={encoded_kw}&location={encoded_city}"
                if url not in seen:
                    seen.add(url)
                    urls.append(url)
    return urls


# ------------------------------------------------------------------
# F4.1 — RSS feed parsing
# ------------------------------------------------------------------

def parse_feed(feed_xml: str) -> list[dict]:
    """Parse RSS XML into a list of partial job dicts.

    Each dict contains: title, company, location, url, date_posted.
    """
    feed = feedparser.parse(feed_xml)
    jobs: list[dict] = []

    for entry in feed.entries:
        title = entry.get("title", "").strip()
        # feedparser puts author in various fields
        company = (
            entry.get("author", "")
            or entry.get("dc_creator", "")
            or ""
        ).strip()

        location = entry.get("location", entry.get("summary", "")).strip()

        link = entry.get("link", "").strip()

        # Parse published date
        date_posted = None
        if entry.get("published"):
            try:
                dt = datetime(*entry.published_parsed[:6])
                date_posted = dt.strftime("%Y-%m-%d")
            except (TypeError, ValueError):
                date_posted = entry.get("published")

        if not link:
            continue

        jobs.append({
            "title": title,
            "company": company,
            "location": location,
            "url": link,
            "date_posted": date_posted,
        })

    return jobs


# ------------------------------------------------------------------
# F4.2 — Job page parser
# ------------------------------------------------------------------

def _is_login_wall(html: str) -> bool:
    """Return True if the HTML appears to be a LinkedIn login wall."""
    html_lower = html.lower()
    return any(marker.lower() in html_lower for marker in _LOGIN_WALL_MARKERS)


def parse_job_page(html: str, url: str = "") -> dict:
    """Parse a LinkedIn job detail page for full fields.

    Returns a dict with: description, qualifications, experience_level,
    language_requirements.  If a login wall is detected, returns partial
    data and logs a warning.
    """
    result: dict = {
        "description": None,
        "qualifications": None,
        "experience_level": None,
        "language_requirements": None,
    }

    if _is_login_wall(html):
        logger.warning("Login wall detected for %s — keeping partial data", url)
        return result

    soup = BeautifulSoup(html, "lxml")

    # Description — usually in a div with class containing "description"
    desc_el = (
        soup.find("div", class_=re.compile(r"description", re.I))
        or soup.find("section", class_=re.compile(r"description", re.I))
    )
    if desc_el:
        result["description"] = desc_el.get_text(separator="\n", strip=True)

    # Qualifications — often in a list under "qualifications" or "criteria"
    qual_el = soup.find("ul", class_=re.compile(r"qualifications|criteria", re.I))
    if qual_el:
        result["qualifications"] = qual_el.get_text(separator="\n", strip=True)

    # Experience level — look for seniority text
    seniority_el = soup.find(
        string=re.compile(r"seniority level|experience level", re.I)
    )
    if seniority_el:
        parent = seniority_el.find_parent()
        if parent:
            sibling = parent.find_next_sibling()
            if sibling:
                result["experience_level"] = sibling.get_text(strip=True)

    # Language requirements — scan description for language mentions
    if result["description"]:
        lang_patterns = re.findall(
            r"(?:english|french|german|deutsch|français|francais)"
            r"(?:\s*(?:required|fluent|native|mandatory|preferred|courant))?",
            result["description"],
            re.I,
        )
        if lang_patterns:
            result["language_requirements"] = ", ".join(lang_patterns)

    return result


# ------------------------------------------------------------------
# Scraper class
# ------------------------------------------------------------------

class LinkedInScraper(BaseScraper):
    """LinkedIn public job scraper using RSS feeds and job page parsing."""

    def __init__(self) -> None:
        super().__init__("linkedin")

    def parse(self, response: requests.Response) -> list[dict]:
        """Parse an RSS feed response."""
        return parse_feed(response.text)

    def scrape(self) -> list[dict]:
        """Scrape all keyword x city RSS feeds and enrich with page details.

        Deduplicates across queries by URL (F4.3).
        """
        urls = build_query_urls()
        all_jobs: list[dict] = []
        seen_urls: set[str] = set()

        for feed_url in urls:
            try:
                response = self.fetch(feed_url)
                jobs = self.parse(response)
            except Exception as exc:
                logger.warning("Feed failed %s: %s", feed_url, exc)
                continue

            for job in jobs:
                job_url = job.get("url", "")
                if job_url in seen_urls:
                    continue
                seen_urls.add(job_url)

                # Enrich with full page data
                try:
                    page_resp = self.fetch(job_url)
                    details = parse_job_page(page_resp.text, job_url)
                    job.update(details)
                except Exception as exc:
                    logger.warning("Job page failed %s: %s", job_url, exc)

                job["source"] = "linkedin"
                job["date_scraped"] = datetime.utcnow().isoformat()
                all_jobs.append(job)

        logger.info("LinkedIn scraper found %d unique jobs", len(all_jobs))
        return all_jobs
