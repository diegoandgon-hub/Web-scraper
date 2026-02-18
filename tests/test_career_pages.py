"""Tests T5.ABB.1-6, T5.SICPA.1-6, T5.Alpiq.1-6, T5.CERN.1-6, T5.Hitachi.1-6 for Task 5: Career Page Scrapers."""

from __future__ import annotations

from job_scraper.scrapers.career_pages.abb import ABBScraper
from job_scraper.scrapers.career_pages.alpiq import AlpiqScraper
from job_scraper.scrapers.career_pages.cern import CERNScraper
from job_scraper.scrapers.career_pages.hitachi import HitachiScraper
from job_scraper.scrapers.career_pages.location import is_romandie, normalize_location
from job_scraper.scrapers.career_pages.sicpa import SICPAScraper


# ------------------------------------------------------------------
# ABB fixtures (Workday JSON API format)
# ------------------------------------------------------------------

ABB_LISTING_RESPONSE = {
    "total": 5,
    "jobPostings": [
        {
            "title": "Process Engineer",
            "externalPath": "/job/Lausanne-VD/Process-Engineer_JR001",
            "locationsText": "Lausanne, Vaud, Switzerland",
            "postedOn": "Posted 3 Days Ago",
            "bulletFields": ["JR001"],
        },
        {
            "title": "Automation Engineer",
            "externalPath": "/job/Geneva-GE/Automation-Engineer_JR002",
            "locationsText": "Geneva, Geneva, Switzerland",
            "postedOn": "Posted 5 Days Ago",
            "bulletFields": ["JR002"],
        },
        {
            "title": "Energy Engineer",
            "externalPath": "/job/Sion-VS/Energy-Engineer_JR003",
            "locationsText": "Sion, Valais, Switzerland",
            "postedOn": "Posted 10 Days Ago",
            "bulletFields": ["JR003"],
        },
    ],
}

ABB_LISTING_PAGE_2 = {
    "total": 5,
    "jobPostings": [
        {
            "title": "Software Engineer",
            "externalPath": "/job/Zurich-ZH/Software-Engineer_JR004",
            "locationsText": "Zurich, Zurich, Switzerland",
        },
        {
            "title": "R&D Engineer",
            "externalPath": "/job/Lausanne-VD/RD-Engineer_JR005",
            "locationsText": "Lausanne, Vaud, Switzerland",
        },
    ],
}

ABB_LISTING_EMPTY = {"total": 0, "jobPostings": []}

ABB_DETAIL_LAUSANNE = {
    "jobPostingInfo": {
        "title": "Process Engineer",
        "jobDescription": (
            "<p>Design chemical processes. English required.</p>"
            "<p><b>Qualifications for the role</b></p>"
            "<ul><li>BSc Chemical Engineering, 0-2 years</li></ul>"
        ),
        "location": "Lausanne, Vaud, Switzerland",
        "startDate": "2026-03-01",
        "timeType": "Full time",
        "externalUrl": "https://abb.wd3.myworkdayjobs.com/External_Career_Page/job/Lausanne",
    },
}

ABB_DETAIL_ZURICH = {
    "jobPostingInfo": {
        "title": "Software Engineer",
        "jobDescription": "<p>Great opportunity in Zurich.</p>",
        "location": "Zurich, Zurich, Switzerland",
        "startDate": "2026-02-01",
    },
}

ABB_DETAIL_MISSING = {
    "jobPostingInfo": {
        "title": "Mystery Role",
    },
}


# ------------------------------------------------------------------
# SICPA fixtures (Taleo HTML format)
# ------------------------------------------------------------------

def _sicpa_listing_html(rows: list[tuple], total: int = 0) -> str:
    """Build a SICPA Taleo listing page with table rows."""
    trs = ""
    for title, dept, loc, date, href in rows:
        trs += f"""<tr class="data-row">
            <td><a href="{href}">{title}</a></td>
            <td>{dept}</td>
            <td>{loc}</td>
            <td>{date}</td>
        </tr>\n"""
    return f"""<html><body>
    <div class="paginationLabel">Results 1 – {len(rows)} of {total}</div>
    <table>{trs}</table>
    </body></html>"""


SICPA_LISTING_PAGE_1 = _sicpa_listing_html([
    ("Process Engineer", "R&D", "Prilly, Switzerland", "15 Feb 2026", "/job/Prilly-Process-Engineer/101/"),
    ("Automation Engineer", "Eng", "Prilly, Switzerland", "14 Feb 2026", "/job/Prilly-Automation-Engineer/102/"),
    ("Data Scientist", "IT", "Springfield, USA", "13 Feb 2026", "/job/Springfield-Data-Scientist/103/"),
], total=5)

SICPA_LISTING_EMPTY = _sicpa_listing_html([], total=0)


def _sicpa_detail_html(
    title: str,
    location: str,
    description: str = "Great opportunity.",
    date_posted: str = "15 Feb 2026",
) -> str:
    return f"""<html><body>
    <h1>{title}</h1>
    <span class="jobGeoLocation">{location}</span>
    <span>Posted on: {date_posted}</span>
    <span class="jobdescription">Long Description\n{description}</span>
    </body></html>"""


SICPA_DETAIL_LAUSANNE = _sicpa_detail_html(
    "Process Engineer", "Lausanne, Switzerland",
    description="Design chemical processes. English required.\nQualifications: BSc Chemical Engineering",
)
SICPA_DETAIL_ZURICH = _sicpa_detail_html(
    "Software Engineer", "Zurich, Switzerland",
)
SICPA_DETAIL_MISSING = """<html><body><h1>Mystery Role</h1></body></html>"""


# ------------------------------------------------------------------
# Alpiq fixtures (SuccessFactors HTML format)
# ------------------------------------------------------------------

def _alpiq_listing_html(jobs: list[tuple], pages: int = 1) -> str:
    """Build an Alpiq listing page with ul.job-item cards."""
    cards = ""
    for title, dept, snippet, loc_contract in jobs:
        cards += f"""<ul class="job-item">
            <div class="content">
                <div class="tag"><span>{dept}</span></div>
                <div class="info">
                    <a class="title" href="/career/open-jobs/your-application/{hash(title) % 10000}">{title}</a>
                    <p class="description">{snippet}</p>
                    <div class="contract">
                        <span>{loc_contract}</span>
                        <span>Permanent</span>
                    </div>
                </div>
            </div>
        </ul>\n"""
    page_links = ""
    for p in range(2, pages + 1):
        page_links += f'<a href="/career/open-jobs/jobs/job-page-{p}/f1-%2A/f2-%2A/search">Page {p}</a>\n'
    return f"<html><body>{cards}{page_links}</body></html>"


ALPIQ_LISTING_PAGE_1 = _alpiq_listing_html([
    ("BESS Project Engineer", "Assets", "Battery storage project.", "Lausanne - 100%"),
    ("OT Network Engineer", "IT", "OT network systems.", "Olten - 100%"),
    ("Asset Manager Hydro", "Assets", "Water management.", "Chur - 80-100%"),
], pages=2)

ALPIQ_LISTING_PAGE_2 = _alpiq_listing_html([
    ("Energy Trader", "Trading", "Energy trading.", "Lausanne - 100%"),
    ("HR Partner", "HR", "Human resources.", "Olten - 80-100%"),
], pages=2)

ALPIQ_LISTING_EMPTY = _alpiq_listing_html([], pages=1)


def _alpiq_detail_html(
    title: str,
    location: str,
    description: str = "Great opportunity.",
) -> str:
    return f"""<html><body>
    <h1>{title}</h1>
    <div class="frame frame-type-successfactors_jobdetail">
        <div class="success-factors">
            <p>Assets</p>
            <p>{location} | Permanent</p>
            <p>{description}</p>
        </div>
    </div>
    </body></html>"""


ALPIQ_DETAIL_LAUSANNE = _alpiq_detail_html(
    "BESS Project Engineer", "Lausanne - 100%",
    description="Design battery storage systems. English required. Qualifications: BSc Electrical Engineering.",
)
ALPIQ_DETAIL_ZURICH = _alpiq_detail_html(
    "Software Engineer", "Zurich - 100%",
)
ALPIQ_DETAIL_MISSING = """<html><body><h1>Mystery Role</h1></body></html>"""


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
# ABB Scraper — T5.ABB.1-T5.ABB.6 (Workday JSON API)
# ==================================================================

class TestABB_1_ListingParsing:
    def test_extracts_job_postings(self):
        postings = ABBScraper.parse_listing(ABB_LISTING_RESPONSE)
        assert len(postings) == 3
        assert postings[0]["title"] == "Process Engineer"

    def test_empty_listing(self):
        assert ABBScraper.parse_listing(ABB_LISTING_EMPTY) == []


class TestABB_2_DetailParsing:
    def test_all_fields_extracted(self):
        job = ABBScraper.parse_detail(ABB_DETAIL_LAUSANNE)
        assert job["title"] == "Process Engineer"
        assert job["company"] == "ABB"
        assert job["location_city"] == "Lausanne"
        assert job["location_canton"] == "VD"
        assert "chemical processes" in job["description"]
        assert "Chemical Engineering" in job["qualifications"]
        assert job["date_posted"] == "2026-03-01"


class TestABB_3_Pagination:
    def test_total_count_extracted(self):
        assert ABBScraper.get_total_count(ABB_LISTING_RESPONSE) == 5

    def test_second_page_has_remaining_jobs(self):
        p1 = ABBScraper.parse_listing(ABB_LISTING_RESPONSE)
        p2 = ABBScraper.parse_listing(ABB_LISTING_PAGE_2)
        assert len(p1) + len(p2) == 5


class TestABB_4_LocationNorm:
    def test_lausanne_mapped(self):
        job = ABBScraper.parse_detail(ABB_DETAIL_LAUSANNE)
        assert job["location_city"] == "Lausanne"
        assert job["location_canton"] == "VD"


class TestABB_5_NonRomandie:
    def test_zurich_not_romandie(self):
        job = ABBScraper.parse_detail(ABB_DETAIL_ZURICH)
        assert not is_romandie(job["location"])


class TestABB_6_MissingFields:
    def test_missing_fields_are_none(self):
        job = ABBScraper.parse_detail(ABB_DETAIL_MISSING)
        assert job["title"] == "Mystery Role"
        assert job["description"] is None
        assert job["qualifications"] is None
        assert job["location_city"] is None
        assert job["location_canton"] is None
        assert job["date_posted"] is None


# ==================================================================
# SICPA Scraper — T5.SICPA.1-T5.SICPA.6 (Taleo HTML)
# ==================================================================

class TestSICPA_1_ListingParsing:
    def test_extracts_job_rows(self):
        listings = SICPAScraper.parse_listing(SICPA_LISTING_PAGE_1)
        assert len(listings) == 3
        assert listings[0]["title"] == "Process Engineer"
        assert listings[0]["location"] == "Prilly, Switzerland"

    def test_empty_listing(self):
        assert SICPAScraper.parse_listing(SICPA_LISTING_EMPTY) == []


class TestSICPA_2_DetailParsing:
    def test_all_fields_extracted(self):
        job = SICPAScraper.parse_detail(SICPA_DETAIL_LAUSANNE)
        assert job["title"] == "Process Engineer"
        assert job["company"] == "SICPA"
        assert job["location_city"] == "Lausanne"
        assert job["location_canton"] == "VD"
        assert "chemical processes" in job["description"]


class TestSICPA_3_Pagination:
    def test_total_count_extracted(self):
        assert SICPAScraper.get_total_count(SICPA_LISTING_PAGE_1) == 5


class TestSICPA_4_LocationNorm:
    def test_lausanne_mapped(self):
        job = SICPAScraper.parse_detail(SICPA_DETAIL_LAUSANNE)
        assert job["location_canton"] == "VD"


class TestSICPA_5_NonRomandie:
    def test_zurich_not_romandie(self):
        job = SICPAScraper.parse_detail(SICPA_DETAIL_ZURICH)
        assert not is_romandie(job["location"])


class TestSICPA_6_MissingFields:
    def test_missing_fields_are_none(self):
        job = SICPAScraper.parse_detail(SICPA_DETAIL_MISSING)
        assert job["title"] == "Mystery Role"
        assert job["description"] is None
        assert job["location_city"] is None


# ==================================================================
# Alpiq Scraper — T5.Alpiq.1-T5.Alpiq.6 (SuccessFactors HTML)
# ==================================================================

class TestAlpiq_1_ListingParsing:
    def test_extracts_job_cards(self):
        listings = AlpiqScraper.parse_listing(ALPIQ_LISTING_PAGE_1)
        assert len(listings) == 3
        assert listings[0]["title"] == "BESS Project Engineer"
        assert listings[0]["department"] == "Assets"

    def test_empty_listing(self):
        assert AlpiqScraper.parse_listing(ALPIQ_LISTING_EMPTY) == []


class TestAlpiq_2_DetailParsing:
    def test_all_fields_extracted(self):
        job = AlpiqScraper.parse_detail(ALPIQ_DETAIL_LAUSANNE)
        assert job["title"] == "BESS Project Engineer"
        assert job["company"] == "Alpiq"
        assert job["location_city"] == "Lausanne"
        assert job["location_canton"] == "VD"
        assert "battery storage" in job["description"]


class TestAlpiq_3_Pagination:
    def test_total_pages_extracted(self):
        assert AlpiqScraper.get_total_count(ALPIQ_LISTING_PAGE_1) == 2


class TestAlpiq_4_LocationNorm:
    def test_lausanne_mapped(self):
        job = AlpiqScraper.parse_detail(ALPIQ_DETAIL_LAUSANNE)
        assert job["location_canton"] == "VD"


class TestAlpiq_5_NonRomandie:
    def test_zurich_not_romandie(self):
        job = AlpiqScraper.parse_detail(ALPIQ_DETAIL_ZURICH)
        assert not is_romandie(job["location"])


class TestAlpiq_6_MissingFields:
    def test_missing_fields_are_none(self):
        job = AlpiqScraper.parse_detail(ALPIQ_DETAIL_MISSING)
        assert job["title"] == "Mystery Role"
        assert job["description"] is None
        assert job["location_city"] is None


# ------------------------------------------------------------------
# CERN fixtures (SmartRecruiters JSON API format)
# ------------------------------------------------------------------

CERN_LISTING_RESPONSE = {
    "totalFound": 65,
    "content": [
        {
            "id": "744000109710867",
            "name": "Mechanical Engineer (BE-GM-FP-2026-31-GRAP)",
            "refNumber": "BE-GM-FP-2026-31-GRAP",
            "location": {"city": "Geneva", "region": "GENEVA", "country": "ch",
                         "remote": False, "hybrid": False},
            "releasedDate": "2026-02-10T10:00:00+00:00",
            "experienceLevel": {"id": "entry_level", "label": "Entry Level"},
            "department": {"id": "934208", "label": "BE"},
            "ref": "https://api.smartrecruiters.com/v1/companies/CERN/postings/744000109710867",
        },
        {
            "id": "744000109710868",
            "name": "Applied Physicist (EP-LBD-2026-49-LD)",
            "refNumber": "EP-LBD-2026-49-LD",
            "location": {"city": "Geneva", "region": "GENEVA", "country": "ch",
                         "remote": False, "hybrid": True},
            "releasedDate": "2026-02-08T10:00:00+00:00",
            "experienceLevel": {"id": "mid_level", "label": "Mid Level"},
            "department": {"id": "934210", "label": "EP"},
            "ref": "https://api.smartrecruiters.com/v1/companies/CERN/postings/744000109710868",
        },
        {
            "id": "744000109710869",
            "name": "Software Engineer (IT-CS-2026-12-LD)",
            "refNumber": "IT-CS-2026-12-LD",
            "location": {"city": "Geneva", "region": "GENEVA", "country": "ch",
                         "remote": False, "hybrid": True},
            "releasedDate": "2026-02-05T10:00:00+00:00",
            "experienceLevel": {"id": "entry_level", "label": "Entry Level"},
            "department": {"id": "934212", "label": "IT"},
            "ref": "https://api.smartrecruiters.com/v1/companies/CERN/postings/744000109710869",
        },
    ],
}

CERN_LISTING_EMPTY = {"totalFound": 0, "content": []}

CERN_DETAIL_GENEVA = {
    "id": "744000109710867",
    "name": "Mechanical Engineer (BE-GM-FP-2026-31-GRAP)",
    "refNumber": "BE-GM-FP-2026-31-GRAP",
    "company": {"identifier": "CERN", "name": "CERN"},
    "location": {"city": "Geneva", "region": "GENEVA", "country": "ch",
                 "remote": False, "hybrid": False,
                 "fullLocation": "Geneva, GENEVA, Switzerland"},
    "releasedDate": "2026-02-10T10:00:00+00:00",
    "experienceLevel": {"id": "entry_level", "label": "Entry Level"},
    "department": {"id": "934208", "label": "BE"},
    "jobAd": {
        "sections": {
            "companyDescription": {"text": ""},
            "jobDescription": {
                "text": (
                    "<p>Design mechanical systems for the Future Circular Collider. "
                    "English required.</p>"
                ),
            },
            "qualifications": {
                "text": "<p>MSc in Mechanical Engineering. 0-2 years experience.</p>",
            },
            "additionalInformation": {
                "text": "<p>Contract duration: 24 months. Salary: 6,372 CHF/month.</p>",
            },
        },
    },
}

CERN_DETAIL_MISSING = {
    "id": "744000000000000",
    "name": "Mystery Role",
    "location": {},
    "jobAd": {"sections": {}},
}


# ------------------------------------------------------------------
# Hitachi Energy fixtures (Workday JSON API format — same as ABB)
# ------------------------------------------------------------------

HITACHI_LISTING_RESPONSE = {
    "total": 144,
    "jobPostings": [
        {
            "title": "Power Electronics Engineer",
            "externalPath": "/job/Baden-Aargau-Switzerland/Power-Electronics-Engineer_R0112345",
            "locationsText": "Baden, Aargau, Switzerland",
            "postedOn": "Posted 3 Days Ago",
            "bulletFields": ["R0112345"],
        },
        {
            "title": "Graduate Trainee - Power Systems",
            "externalPath": "/job/Zurich-Switzerland/Graduate-Trainee_R0112346",
            "locationsText": "Zurich, Zurich, Switzerland",
            "postedOn": "Posted 5 Days Ago",
            "bulletFields": ["R0112346"],
        },
        {
            "title": "Electrical Engineer",
            "externalPath": "/job/Geneva-Switzerland/Electrical-Engineer_R0112347",
            "locationsText": "Geneva, Geneva, Switzerland",
            "postedOn": "Posted 10 Days Ago",
            "bulletFields": ["R0112347"],
        },
    ],
}

HITACHI_LISTING_EMPTY = {"total": 0, "jobPostings": []}

HITACHI_DETAIL_BADEN = {
    "jobPostingInfo": {
        "title": "Power Electronics Engineer",
        "jobDescription": (
            "<p>Design power electronics for grid solutions. English required.</p>"
            "<p><b>Requirements</b></p>"
            "<ul><li>MSc Electrical Engineering, 2-5 years</li></ul>"
        ),
        "location": "Baden, Aargau, Switzerland",
        "startDate": "2026-04-01",
    },
}

HITACHI_DETAIL_GENEVA = {
    "jobPostingInfo": {
        "title": "Electrical Engineer",
        "jobDescription": (
            "<p>Join our grid integration team in Geneva. English required.</p>"
            "<p><b>Your profile</b></p>"
            "<ul><li>BSc Electrical Engineering, 0-2 years</li></ul>"
        ),
        "location": "Geneva, Geneva, Switzerland",
        "startDate": "2026-03-15",
    },
}

HITACHI_DETAIL_MISSING = {
    "jobPostingInfo": {
        "title": "Mystery Role",
    },
}


# ==================================================================
# CERN Scraper — T5.CERN.1-T5.CERN.6 (SmartRecruiters JSON API)
# ==================================================================

class TestCERN_1_ListingParsing:
    def test_extracts_job_postings(self):
        postings = CERNScraper.parse_listing(CERN_LISTING_RESPONSE)
        assert len(postings) == 3
        assert postings[0]["name"] == "Mechanical Engineer (BE-GM-FP-2026-31-GRAP)"

    def test_empty_listing(self):
        assert CERNScraper.parse_listing(CERN_LISTING_EMPTY) == []


class TestCERN_2_DetailParsing:
    def test_all_fields_extracted(self):
        job = CERNScraper.parse_detail(CERN_DETAIL_GENEVA)
        assert job["title"] == "Mechanical Engineer (BE-GM-FP-2026-31-GRAP)"
        assert job["company"] == "CERN"
        assert job["location_city"] == "Geneva"
        assert job["location_canton"] == "GE"
        assert "Future Circular Collider" in job["description"]
        assert "Mechanical Engineering" in job["qualifications"]
        assert job["date_posted"] == "2026-02-10"
        assert job["experience_level"] == "Entry Level"

    def test_language_extracted(self):
        job = CERNScraper.parse_detail(CERN_DETAIL_GENEVA)
        assert "English" in (job["language_requirements"] or "")


class TestCERN_3_Pagination:
    def test_total_count_extracted(self):
        assert CERNScraper.get_total_count(CERN_LISTING_RESPONSE) == 65

    def test_empty_total(self):
        assert CERNScraper.get_total_count(CERN_LISTING_EMPTY) == 0


class TestCERN_4_LocationNorm:
    def test_geneva_mapped(self):
        job = CERNScraper.parse_detail(CERN_DETAIL_GENEVA)
        assert job["location_city"] == "Geneva"
        assert job["location_canton"] == "GE"


class TestCERN_5_NonRomandie:
    def test_geneva_is_romandie(self):
        job = CERNScraper.parse_detail(CERN_DETAIL_GENEVA)
        assert is_romandie(job["location"])


class TestCERN_6_MissingFields:
    def test_missing_fields_are_none(self):
        job = CERNScraper.parse_detail(CERN_DETAIL_MISSING)
        assert job["title"] == "Mystery Role"
        assert job["description"] is None
        assert job["qualifications"] is None
        assert job["location_city"] is None
        assert job["location_canton"] is None
        assert job["date_posted"] is None


# ==================================================================
# Hitachi Scraper — T5.Hitachi.1-T5.Hitachi.6 (Workday JSON API)
# ==================================================================

class TestHitachi_1_ListingParsing:
    def test_extracts_job_postings(self):
        postings = HitachiScraper.parse_listing(HITACHI_LISTING_RESPONSE)
        assert len(postings) == 3
        assert postings[0]["title"] == "Power Electronics Engineer"

    def test_empty_listing(self):
        assert HitachiScraper.parse_listing(HITACHI_LISTING_EMPTY) == []


class TestHitachi_2_DetailParsing:
    def test_all_fields_extracted(self):
        job = HitachiScraper.parse_detail(HITACHI_DETAIL_GENEVA)
        assert job["title"] == "Electrical Engineer"
        assert job["company"] == "Hitachi Energy"
        assert job["location_city"] == "Geneva"
        assert job["location_canton"] == "GE"
        assert "grid integration" in job["description"]
        assert "Electrical Engineering" in job["qualifications"]
        assert job["date_posted"] == "2026-03-15"

    def test_language_extracted(self):
        job = HitachiScraper.parse_detail(HITACHI_DETAIL_GENEVA)
        assert "English" in (job["language_requirements"] or "")


class TestHitachi_3_Pagination:
    def test_total_count_extracted(self):
        assert HitachiScraper.get_total_count(HITACHI_LISTING_RESPONSE) == 144

    def test_empty_total(self):
        assert HitachiScraper.get_total_count(HITACHI_LISTING_EMPTY) == 0


class TestHitachi_4_LocationNorm:
    def test_geneva_mapped(self):
        job = HitachiScraper.parse_detail(HITACHI_DETAIL_GENEVA)
        assert job["location_city"] == "Geneva"
        assert job["location_canton"] == "GE"


class TestHitachi_5_NonRomandie:
    def test_baden_not_romandie(self):
        job = HitachiScraper.parse_detail(HITACHI_DETAIL_BADEN)
        assert not is_romandie(job["location"])


class TestHitachi_6_MissingFields:
    def test_missing_fields_are_none(self):
        job = HitachiScraper.parse_detail(HITACHI_DETAIL_MISSING)
        assert job["title"] == "Mystery Role"
        assert job["description"] is None
        assert job["qualifications"] is None
        assert job["location_city"] is None
        assert job["location_canton"] is None
        assert job["date_posted"] is None
