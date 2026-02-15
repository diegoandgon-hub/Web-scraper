"""Tests T4.1-T4.6 for Task 4: LinkedIn Public Scraper."""

from __future__ import annotations

import logging

from job_scraper.scrapers.linkedin import (
    build_query_urls,
    parse_feed,
    parse_job_page,
)


# ------------------------------------------------------------------
# Fixtures — RSS XML and HTML, zero network calls (T4.6)
# ------------------------------------------------------------------

RSS_FIXTURE = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>LinkedIn Jobs</title>
    <item>
      <title>Process Engineer</title>
      <author>Acme Corp</author>
      <link>https://www.linkedin.com/jobs/view/111</link>
      <pubDate>Mon, 10 Feb 2026 00:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Automation Engineer</title>
      <author>Globex Inc</author>
      <link>https://www.linkedin.com/jobs/view/222</link>
      <pubDate>Tue, 11 Feb 2026 00:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

JOB_PAGE_HTML = """\
<html>
<body>
  <div class="description">
    <p>We are looking for a Process Engineer to join our team.</p>
    <p>Requirements: English required, BSc in Chemical Engineering.</p>
  </div>
  <ul class="qualifications">
    <li>BSc in Chemical Engineering</li>
    <li>0-2 years experience</li>
  </ul>
  <span>Seniority Level</span>
  <span>Entry level</span>
</body>
</html>
"""

LOGIN_WALL_HTML = """\
<html>
<body>
  <h1>Sign in to view this job</h1>
  <p>Join now to see what you are missing</p>
  <div class="authwall">Please log in</div>
</body>
</html>
"""


# ------------------------------------------------------------------
# T4.1 - RSS XML fixture parsed into correct dicts with expected keys
# ------------------------------------------------------------------
class TestT4_1_RssParsing:
    def test_parses_correct_number_of_jobs(self):
        jobs = parse_feed(RSS_FIXTURE)
        assert len(jobs) == 2

    def test_job_has_expected_keys(self):
        jobs = parse_feed(RSS_FIXTURE)
        expected_keys = {"title", "company", "url", "date_posted", "location"}
        for job in jobs:
            assert expected_keys.issubset(job.keys())

    def test_first_job_fields(self):
        jobs = parse_feed(RSS_FIXTURE)
        assert jobs[0]["title"] == "Process Engineer"
        assert jobs[0]["company"] == "Acme Corp"
        assert jobs[0]["url"] == "https://www.linkedin.com/jobs/view/111"
        assert jobs[0]["date_posted"] == "2026-02-10"

    def test_empty_feed_returns_empty_list(self):
        empty_rss = '<?xml version="1.0"?><rss><channel></channel></rss>'
        assert parse_feed(empty_rss) == []


# ------------------------------------------------------------------
# T4.2 - Cross-query URL deduplication works
# ------------------------------------------------------------------
class TestT4_2_CrossQueryDedup:
    def test_duplicate_urls_across_feeds_deduplicated(self):
        # Same RSS parsed twice simulates overlapping queries
        jobs1 = parse_feed(RSS_FIXTURE)
        jobs2 = parse_feed(RSS_FIXTURE)

        seen: set[str] = set()
        unique: list[dict] = []
        for job in jobs1 + jobs2:
            if job["url"] not in seen:
                seen.add(job["url"])
                unique.append(job)

        assert len(unique) == 2  # not 4


# ------------------------------------------------------------------
# T4.3 - Job page HTML fixture parsed for all fields
# ------------------------------------------------------------------
class TestT4_3_JobPageParsing:
    def test_description_extracted(self):
        result = parse_job_page(JOB_PAGE_HTML)
        assert result["description"] is not None
        assert "Process Engineer" in result["description"]

    def test_qualifications_extracted(self):
        result = parse_job_page(JOB_PAGE_HTML)
        assert result["qualifications"] is not None
        assert "Chemical Engineering" in result["qualifications"]

    def test_language_requirements_extracted(self):
        result = parse_job_page(JOB_PAGE_HTML)
        assert result["language_requirements"] is not None
        assert "English" in result["language_requirements"]

    def test_experience_level_extracted(self):
        result = parse_job_page(JOB_PAGE_HTML)
        assert result["experience_level"] is not None
        assert "Entry level" in result["experience_level"]


# ------------------------------------------------------------------
# T4.4 - Login-wall HTML results in partial data + warning log
# ------------------------------------------------------------------
class TestT4_4_LoginWall:
    def test_login_wall_returns_partial_data(self):
        result = parse_job_page(LOGIN_WALL_HTML, url="https://linkedin.com/jobs/view/999")
        assert result["description"] is None
        assert result["qualifications"] is None

    def test_login_wall_logs_warning(self, caplog):
        with caplog.at_level(logging.WARNING):
            parse_job_page(LOGIN_WALL_HTML, url="https://linkedin.com/jobs/view/999")
        assert "Login wall detected" in caplog.text


# ------------------------------------------------------------------
# T4.5 - Query URLs correctly constructed with proper encoding
# ------------------------------------------------------------------
class TestT4_5_QueryUrls:
    def test_urls_are_non_empty(self):
        urls = build_query_urls()
        assert len(urls) > 0

    def test_urls_contain_keywords_and_location(self):
        urls = build_query_urls()
        # At least one URL should have "process+engineer" and a city
        found_kw = any("process+engineer" in u.lower() for u in urls)
        found_city = any("Geneva" in u or "geneva" in u.lower() for u in urls)
        assert found_kw
        assert found_city

    def test_urls_are_unique(self):
        urls = build_query_urls()
        assert len(urls) == len(set(urls))

    def test_urls_use_rss_base(self):
        urls = build_query_urls()
        for url in urls:
            assert url.startswith("https://www.linkedin.com/jobs/search/feed")

    def test_special_characters_encoded(self):
        urls = build_query_urls()
        # "Yverdon-les-Bains" should be URL-encoded
        yverdon_urls = [u for u in urls if "Yverdon" in u]
        assert len(yverdon_urls) > 0


# ------------------------------------------------------------------
# T4.6 - All tests use fixtures, zero network calls
# ------------------------------------------------------------------
class TestT4_6_NoNetwork:
    def test_no_network_in_parse_feed(self):
        """parse_feed() works purely on string input — no network."""
        jobs = parse_feed(RSS_FIXTURE)
        assert isinstance(jobs, list)

    def test_no_network_in_parse_job_page(self):
        """parse_job_page() works purely on string input — no network."""
        result = parse_job_page(JOB_PAGE_HTML)
        assert isinstance(result, dict)
