"""Tests T3.1-T3.7 for Task 3: Core Scraping Engine (BaseScraper)."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from job_scraper.scrapers.base import BaseScraper
from job_scraper.scrapers.exceptions import ParseError, ScrapingError


# Concrete subclass for testing
class _DummyScraper(BaseScraper):
    def parse(self, response):
        return [{"title": "Test Job"}]

    def scrape(self):
        resp = self.fetch("https://example.com/jobs")
        return self.parse(resp)


def _mock_response(status_code=200, text="OK"):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.text = text
    return resp


# ---------------------------------------------------------------------------
# T3.1 - BaseScraper cannot be instantiated directly (abstract)
# ---------------------------------------------------------------------------
class TestT3_1_Abstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            BaseScraper("test")

    def test_concrete_subclass_instantiates(self):
        scraper = _DummyScraper("test")
        assert scraper.source_name == "test"


# ---------------------------------------------------------------------------
# T3.2 - Concrete subclass fetch() returns Response (mocked requests.get)
# ---------------------------------------------------------------------------
class TestT3_2_Fetch:
    @patch("job_scraper.scrapers.base.time.sleep")
    @patch("job_scraper.scrapers.base.is_allowed", return_value=True)
    def test_fetch_returns_response(self, _mock_robots, _mock_sleep):
        scraper = _DummyScraper("test")
        mock_resp = _mock_response(200, "<html>jobs</html>")
        scraper.session.get = MagicMock(return_value=mock_resp)

        result = scraper.fetch("https://example.com/jobs")

        assert result.status_code == 200
        scraper.session.get.assert_called_once_with(
            "https://example.com/jobs", timeout=30
        )


# ---------------------------------------------------------------------------
# T3.3 - Retry on 429, succeeds on second attempt
# ---------------------------------------------------------------------------
class TestT3_3_Retry429:
    @patch("job_scraper.scrapers.base.time.sleep")
    @patch("job_scraper.scrapers.base.is_allowed", return_value=True)
    def test_retries_on_429_then_succeeds(self, _mock_robots, mock_sleep):
        scraper = _DummyScraper("test")
        resp_429 = _mock_response(429)
        resp_200 = _mock_response(200)
        scraper.session.get = MagicMock(side_effect=[resp_429, resp_200])

        result = scraper.fetch("https://example.com/jobs")

        assert result.status_code == 200
        assert scraper.session.get.call_count == 2


# ---------------------------------------------------------------------------
# T3.4 - ScrapingError raised after 3 consecutive 5xx
# ---------------------------------------------------------------------------
class TestT3_4_ScrapingErrorAfterRetries:
    @patch("job_scraper.scrapers.base.time.sleep")
    @patch("job_scraper.scrapers.base.is_allowed", return_value=True)
    def test_raises_after_3_consecutive_5xx(self, _mock_robots, _mock_sleep):
        scraper = _DummyScraper("test")
        resp_500 = _mock_response(500)
        scraper.session.get = MagicMock(return_value=resp_500)

        with pytest.raises(ScrapingError, match="500 after 3 retries"):
            scraper.fetch("https://example.com/jobs")

        assert scraper.session.get.call_count == 3


# ---------------------------------------------------------------------------
# T3.5 - URL skipped when robots.txt disallows
# ---------------------------------------------------------------------------
class TestT3_5_RobotsDisallow:
    @patch("job_scraper.scrapers.base.time.sleep")
    @patch("job_scraper.scrapers.base.is_allowed", return_value=False)
    def test_raises_when_robots_disallows(self, _mock_robots, _mock_sleep):
        scraper = _DummyScraper("test")

        with pytest.raises(ScrapingError, match="robots.txt disallows"):
            scraper.fetch("https://example.com/private")


# ---------------------------------------------------------------------------
# T3.6 - Delay between calls respected (mock time.sleep)
# ---------------------------------------------------------------------------
class TestT3_6_Delay:
    @patch("job_scraper.scrapers.base.time.sleep")
    @patch("job_scraper.scrapers.base.is_allowed", return_value=True)
    def test_delay_called(self, _mock_robots, mock_sleep):
        scraper = _DummyScraper("test")
        scraper.session.get = MagicMock(return_value=_mock_response(200))

        scraper.fetch("https://example.com/jobs")

        # time.sleep should be called with REQUEST_DELAY_SECONDS
        mock_sleep.assert_any_call(2)


# ---------------------------------------------------------------------------
# T3.7 - User-agent rotates between consecutive calls
# ---------------------------------------------------------------------------
class TestT3_7_UserAgentRotation:
    @patch("job_scraper.scrapers.base.time.sleep")
    @patch("job_scraper.scrapers.base.is_allowed", return_value=True)
    def test_user_agent_changes_on_fetch(self, _mock_robots, _mock_sleep):
        scraper = _DummyScraper("test")
        scraper.session.get = MagicMock(return_value=_mock_response(200))

        # Force a known UA, then fetch — UA should rotate
        scraper.session.headers["User-Agent"] = "InitialAgent"
        scraper.fetch("https://example.com/jobs")

        # After fetch, User-Agent should have been rotated (different from
        # "InitialAgent" with overwhelming probability given 5 real UAs)
        new_ua = scraper.session.headers["User-Agent"]
        assert new_ua != "InitialAgent"
        assert "Mozilla" in new_ua


# ---------------------------------------------------------------------------
# Extra: ParseError is importable and is an Exception subclass
# ---------------------------------------------------------------------------
class TestExceptions:
    def test_scraping_error_is_exception(self):
        assert issubclass(ScrapingError, Exception)

    def test_parse_error_is_exception(self):
        assert issubclass(ParseError, Exception)
