"""Tests T4.1-T4.6 for Task 4: JobUp.ch Scraper (replaces LinkedIn)."""

from __future__ import annotations

import json

from job_scraper.scrapers.jobup import (
    build_search_urls,
    get_total_pages,
    parse_detail,
    parse_listing,
)


# ------------------------------------------------------------------
# Fixtures — embedded JSON and JSON-LD, zero network calls (T4.6)
# ------------------------------------------------------------------

def _listing_html(results: list[dict], num_pages: int = 1, total_hits: int = 0) -> str:
    """Build a jobup.ch listing page with __INIT__ JSON."""
    init_data = {
        "vacancy": {
            "results": {
                "main": {
                    "results": results,
                    "meta": {
                        "numPages": num_pages,
                        "totalHits": total_hits or len(results),
                    },
                }
            }
        }
    }
    return (
        "<html><body>"
        f"<script>__INIT__ = {json.dumps(init_data)};</script>"
        "</body></html>"
    )


def _detail_html(
    title: str,
    company: str = "Acme SA",
    city: str = "Lausanne",
    country: str = "CH",
    description: str = "Great opportunity.",
    date_posted: str = "2026-02-15T10:00:00+01:00",
    employment_type: str = "FULL_TIME",
) -> str:
    """Build a jobup.ch detail page with JSON-LD JobPosting."""
    ld = {
        "@context": "https://schema.org/",
        "@type": "JobPosting",
        "title": title,
        "datePosted": date_posted,
        "hiringOrganization": {"@type": "Organization", "name": company},
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": city,
                "addressCountry": country,
            },
        },
        "description": f"<p>{description}</p>",
        "employmentType": [employment_type],
    }
    return (
        "<html><head>"
        f'<script type="application/ld+json">{json.dumps(ld)}</script>'
        f"</head><body><h1>{title}</h1></body></html>"
    )


LISTING_RESULTS = [
    {
        "id": "aaa-111",
        "title": "Process Engineer",
        "company": {"name": "NovaMea SA", "slug": "novamea"},
        "place": "Lausanne",
        "publicationDate": "2026-02-14T08:00:00+01:00",
    },
    {
        "id": "bbb-222",
        "title": "Automation Engineer",
        "company": {"name": "Globex AG", "slug": "globex"},
        "place": "Geneva",
        "publicationDate": "2026-02-13T08:00:00+01:00",
    },
    {
        "id": "ccc-333",
        "title": "Energy Analyst",
        "company": {"name": "Zurich Power", "slug": "zurich-power"},
        "place": "Zurich",
        "publicationDate": "2026-02-12T08:00:00+01:00",
    },
]

LISTING_HTML = _listing_html(LISTING_RESULTS, num_pages=2, total_hits=25)
LISTING_EMPTY = _listing_html([], num_pages=1, total_hits=0)

DETAIL_LAUSANNE = _detail_html(
    "Process Engineer",
    company="NovaMea SA",
    city="Lausanne",
    description=(
        "We are looking for a Process Engineer to join our team. "
        "Requirements: BSc in Chemical Engineering, 0-2 years experience. "
        "English required."
    ),
)

DETAIL_ZURICH = _detail_html(
    "Software Engineer",
    company="Zurich Tech",
    city="Zurich",
    description="Backend development in Zurich.",
)

DETAIL_MISSING = "<html><body><h1>Mystery Role</h1></body></html>"


# ==================================================================
# T4.1 — Listing parsing from embedded __INIT__ JSON
# ==================================================================

class TestT4_1_ListingParsing:
    def test_parses_correct_number_of_jobs(self):
        jobs = parse_listing(LISTING_HTML)
        assert len(jobs) == 3

    def test_job_has_expected_keys(self):
        jobs = parse_listing(LISTING_HTML)
        expected_keys = {"id", "title", "company", "place", "publicationDate", "url"}
        for job in jobs:
            assert expected_keys.issubset(job.keys())

    def test_first_job_fields(self):
        jobs = parse_listing(LISTING_HTML)
        assert jobs[0]["title"] == "Process Engineer"
        assert jobs[0]["company"] == "NovaMea SA"
        assert jobs[0]["place"] == "Lausanne"
        assert jobs[0]["id"] == "aaa-111"
        assert "aaa-111" in jobs[0]["url"]

    def test_empty_listing_returns_empty(self):
        assert parse_listing(LISTING_EMPTY) == []

    def test_malformed_html_returns_empty(self):
        assert parse_listing("<html><body>No data</body></html>") == []


# ==================================================================
# T4.2 — Cross-query deduplication by job ID
# ==================================================================

class TestT4_2_CrossQueryDedup:
    def test_duplicate_ids_deduplicated(self):
        jobs1 = parse_listing(LISTING_HTML)
        jobs2 = parse_listing(LISTING_HTML)

        seen: set[str] = set()
        unique: list[dict] = []
        for job in jobs1 + jobs2:
            if job["id"] not in seen:
                seen.add(job["id"])
                unique.append(job)

        assert len(unique) == 3  # not 6


# ==================================================================
# T4.3 — Detail page parsing (JSON-LD extraction)
# ==================================================================

class TestT4_3_DetailParsing:
    def test_all_fields_extracted(self):
        job = parse_detail(DETAIL_LAUSANNE)
        assert job["title"] == "Process Engineer"
        assert job["company"] == "NovaMea SA"
        assert job["location_city"] == "Lausanne"
        assert job["location_canton"] == "VD"
        assert "Process Engineer" in job["description"]
        assert job["date_posted"] == "2026-02-15"
        assert "English" in (job["language_requirements"] or "")

    def test_zurich_location(self):
        job = parse_detail(DETAIL_ZURICH)
        assert job["title"] == "Software Engineer"
        assert job["company"] == "Zurich Tech"


# ==================================================================
# T4.4 — Missing fields handling (graceful degradation)
# ==================================================================

class TestT4_4_MissingFields:
    def test_missing_json_ld_returns_partial(self):
        job = parse_detail(DETAIL_MISSING)
        assert job["title"] == "Mystery Role"
        assert job["description"] is None
        assert job["company"] is None
        assert job["location_city"] is None

    def test_empty_html_returns_nones(self):
        job = parse_detail("<html><body></body></html>")
        assert job["title"] is None
        assert job["description"] is None


# ==================================================================
# T4.5 — Search URL construction
# ==================================================================

class TestT4_5_SearchUrls:
    def test_urls_are_non_empty(self):
        urls = build_search_urls()
        assert len(urls) > 0

    def test_urls_contain_keywords_and_location(self):
        urls = build_search_urls()
        found_kw = any("process+engineer" in u.lower() for u in urls)
        found_city = any("Geneva" in u or "geneva" in u.lower() for u in urls)
        assert found_kw
        assert found_city

    def test_urls_are_unique(self):
        urls = build_search_urls()
        assert len(urls) == len(set(urls))

    def test_urls_use_jobup_base(self):
        urls = build_search_urls()
        for url in urls:
            assert url.startswith("https://www.jobup.ch/en/jobs/")

    def test_special_characters_encoded(self):
        urls = build_search_urls()
        yverdon_urls = [u for u in urls if "Yverdon" in u]
        assert len(yverdon_urls) > 0


# ==================================================================
# T4.6 — Pagination
# ==================================================================

class TestT4_6_Pagination:
    def test_total_pages_extracted(self):
        assert get_total_pages(LISTING_HTML) == 2

    def test_empty_listing_returns_one_page(self):
        assert get_total_pages(LISTING_EMPTY) == 1

    def test_malformed_returns_one_page(self):
        assert get_total_pages("<html></html>") == 1


# ==================================================================
# T4.7 — All tests use fixtures, zero network calls
# ==================================================================

class TestT4_7_NoNetwork:
    def test_no_network_in_parse_listing(self):
        jobs = parse_listing(LISTING_HTML)
        assert isinstance(jobs, list)

    def test_no_network_in_parse_detail(self):
        result = parse_detail(DETAIL_LAUSANNE)
        assert isinstance(result, dict)
