"""Tests T5.ABB.1-6, T5.SICPA.1-6, T5.Alpiq.1-6 for Task 5: Career Page Scrapers."""

from __future__ import annotations

from job_scraper.scrapers.career_pages.abb import ABBScraper
from job_scraper.scrapers.career_pages.alpiq import AlpiqScraper
from job_scraper.scrapers.career_pages.location import is_romandie, normalize_location
from job_scraper.scrapers.career_pages.sicpa import SICPAScraper


# ------------------------------------------------------------------
# HTML fixtures (shared structure, company-specific markers)
# ------------------------------------------------------------------

def _listing_html(job_hrefs: list[str], total: int = 0) -> str:
    links = "\n".join(f'<a href="{h}">Job</a>' for h in job_hrefs)
    return f"""<html><body>
    <div>{total} results</div>
    {links}
    </body></html>"""


def _detail_html(
    title: str,
    location: str,
    description: str = "Great opportunity.",
    qualifications: str = "BSc required",
    date_posted: str | None = "2026-03-01",
) -> str:
    date_section = ""
    if date_posted:
        date_section = f'<span>Date posted: {date_posted}</span>'
    return f"""<html><body>
    <h1>{title}</h1>
    <span class="location">{location}</span>
    <div class="description">{description}</div>
    <div class="qualifications">{qualifications}</div>
    {date_section}
    </body></html>"""


LISTING_PAGE_1 = _listing_html(
    ["/job/101", "/job/102", "/job/103"], total=5
)
LISTING_PAGE_2 = _listing_html(
    ["/job/104", "/job/105"], total=5
)
LISTING_EMPTY = _listing_html([], total=0)

DETAIL_LAUSANNE = _detail_html(
    "Process Engineer", "Lausanne, Switzerland",
    description="Design chemical processes. English required.",
    qualifications="BSc Chemical Engineering, 0-2 years",
)
DETAIL_ZURICH = _detail_html(
    "Software Engineer", "Zurich, Switzerland",
)
DETAIL_MISSING = """<html><body><h1>Mystery Role</h1></body></html>"""


# ==================================================================
# Location normalization (shared by all three scrapers)
# ==================================================================

class TestLocationNormalization:
    # T5.X.4
    def test_lausanne_normalizes_to_vd(self):
        city, canton = normalize_location("Lausanne, Switzerland")
        assert city == "Lausanne"
        assert canton == "VD"

    def test_geneva_normalizes_to_ge(self):
        city, canton = normalize_location("Geneva")
        assert city == "Geneva"
        assert canton == "GE"

    def test_sion_normalizes_to_vs(self):
        city, canton = normalize_location("Sion, CH")
        assert city == "Sion"
        assert canton == "VS"

    # T5.X.5
    def test_zurich_not_romandie(self):
        assert is_romandie("Zurich, Switzerland") is False

    def test_basel_not_romandie(self):
        assert is_romandie("Basel") is False

    def test_empty_string(self):
        city, canton = normalize_location("")
        assert city is None
        assert canton is None


# ==================================================================
# ABB Scraper — T5.ABB.1-T5.ABB.6
# ==================================================================

class TestABB_1_ListingParsing:
    def test_extracts_job_urls(self):
        urls = ABBScraper.parse_listing(LISTING_PAGE_1)
        assert urls == ["/job/101", "/job/102", "/job/103"]

    def test_empty_listing(self):
        assert ABBScraper.parse_listing(LISTING_EMPTY) == []


class TestABB_2_DetailParsing:
    def test_all_fields_extracted(self):
        job = ABBScraper.parse_detail(DETAIL_LAUSANNE)
        assert job["title"] == "Process Engineer"
        assert job["company"] == "ABB"
        assert job["location_city"] == "Lausanne"
        assert job["location_canton"] == "VD"
        assert "chemical processes" in job["description"]
        assert "Chemical Engineering" in job["qualifications"]
        assert job["date_posted"] == "2026-03-01"


class TestABB_3_Pagination:
    def test_total_count_extracted(self):
        assert ABBScraper.get_total_count(LISTING_PAGE_1) == 5

    def test_second_page_has_remaining_jobs(self):
        urls1 = ABBScraper.parse_listing(LISTING_PAGE_1)
        urls2 = ABBScraper.parse_listing(LISTING_PAGE_2)
        assert len(urls1) + len(urls2) == 5


class TestABB_4_LocationNorm:
    def test_lausanne_mapped(self):
        job = ABBScraper.parse_detail(DETAIL_LAUSANNE)
        assert job["location_city"] == "Lausanne"
        assert job["location_canton"] == "VD"


class TestABB_5_NonRomandie:
    def test_zurich_not_romandie(self):
        job = ABBScraper.parse_detail(DETAIL_ZURICH)
        assert not is_romandie(job["location"])


class TestABB_6_MissingFields:
    def test_missing_fields_are_none(self):
        job = ABBScraper.parse_detail(DETAIL_MISSING)
        assert job["title"] == "Mystery Role"
        assert job["description"] is None
        assert job["qualifications"] is None
        assert job["location_city"] is None
        assert job["location_canton"] is None
        assert job["date_posted"] is None


# ==================================================================
# SICPA Scraper — T5.SICPA.1-T5.SICPA.6
# ==================================================================

class TestSICPA_1_ListingParsing:
    def test_extracts_job_urls(self):
        urls = SICPAScraper.parse_listing(LISTING_PAGE_1)
        assert urls == ["/job/101", "/job/102", "/job/103"]

    def test_empty_listing(self):
        assert SICPAScraper.parse_listing(LISTING_EMPTY) == []


class TestSICPA_2_DetailParsing:
    def test_all_fields_extracted(self):
        job = SICPAScraper.parse_detail(DETAIL_LAUSANNE)
        assert job["title"] == "Process Engineer"
        assert job["company"] == "SICPA"
        assert job["location_city"] == "Lausanne"
        assert job["location_canton"] == "VD"
        assert "chemical processes" in job["description"]


class TestSICPA_3_Pagination:
    def test_total_count_extracted(self):
        assert SICPAScraper.get_total_count(LISTING_PAGE_1) == 5


class TestSICPA_4_LocationNorm:
    def test_lausanne_mapped(self):
        job = SICPAScraper.parse_detail(DETAIL_LAUSANNE)
        assert job["location_canton"] == "VD"


class TestSICPA_5_NonRomandie:
    def test_zurich_not_romandie(self):
        job = SICPAScraper.parse_detail(DETAIL_ZURICH)
        assert not is_romandie(job["location"])


class TestSICPA_6_MissingFields:
    def test_missing_fields_are_none(self):
        job = SICPAScraper.parse_detail(DETAIL_MISSING)
        assert job["title"] == "Mystery Role"
        assert job["description"] is None
        assert job["location_city"] is None


# ==================================================================
# Alpiq Scraper — T5.Alpiq.1-T5.Alpiq.6
# ==================================================================

class TestAlpiq_1_ListingParsing:
    def test_extracts_job_urls(self):
        urls = AlpiqScraper.parse_listing(LISTING_PAGE_1)
        assert urls == ["/job/101", "/job/102", "/job/103"]

    def test_empty_listing(self):
        assert AlpiqScraper.parse_listing(LISTING_EMPTY) == []


class TestAlpiq_2_DetailParsing:
    def test_all_fields_extracted(self):
        job = AlpiqScraper.parse_detail(DETAIL_LAUSANNE)
        assert job["title"] == "Process Engineer"
        assert job["company"] == "Alpiq"
        assert job["location_city"] == "Lausanne"
        assert job["location_canton"] == "VD"
        assert "chemical processes" in job["description"]


class TestAlpiq_3_Pagination:
    def test_total_count_extracted(self):
        assert AlpiqScraper.get_total_count(LISTING_PAGE_1) == 5


class TestAlpiq_4_LocationNorm:
    def test_lausanne_mapped(self):
        job = AlpiqScraper.parse_detail(DETAIL_LAUSANNE)
        assert job["location_canton"] == "VD"


class TestAlpiq_5_NonRomandie:
    def test_zurich_not_romandie(self):
        job = AlpiqScraper.parse_detail(DETAIL_ZURICH)
        assert not is_romandie(job["location"])


class TestAlpiq_6_MissingFields:
    def test_missing_fields_are_none(self):
        job = AlpiqScraper.parse_detail(DETAIL_MISSING)
        assert job["title"] == "Mystery Role"
        assert job["description"] is None
        assert job["location_city"] is None
