"""Tests T1.1-T1.5 for Task 1: Project Setup & Configuration."""

from unittest.mock import MagicMock, patch
from urllib.robotparser import RobotFileParser

from job_scraper import config
from job_scraper.robots import clear_cache, is_allowed


# T1.1 - Config loads all expected keys; missing Claude key only errors when LLM filter is invoked
class TestT1_1_ConfigKeys:
    def test_all_expected_keys_exist(self):
        expected = [
            "DATABASE_PATH",
            "OUTPUT_DIR",
            "ROMANDIE_CANTONS",
            "ROMANDIE_CITIES",
            "TARGET_KEYWORDS",
            "LANGUAGE_EXCLUDE_PATTERNS",
            "ENTRY_LEVEL_PATTERNS",
            "SENIOR_EXCLUDE_PATTERNS",
            "ENROLLMENT_EXCLUDE_PATTERNS",
            "REQUEST_DELAY_SECONDS",
            "USER_AGENTS",
            "CLAUDE_API_KEY",
            "CLAUDE_MODEL",
            "LOG_LEVEL",
        ]
        for key in expected:
            assert hasattr(config, key), f"config missing expected key: {key}"

    def test_missing_claude_key_does_not_error_on_import(self):
        # The config module should load fine even without ANTHROPIC_API_KEY set.
        # CLAUDE_API_KEY defaults to empty string.
        assert isinstance(config.CLAUDE_API_KEY, str)


# T1.2 - ROMANDIE_CANTONS has exactly 6 two-letter codes
class TestT1_2_RomandieCantons:
    def test_exactly_six_cantons(self):
        assert len(config.ROMANDIE_CANTONS) == 6

    def test_all_two_letter_codes(self):
        for canton in config.ROMANDIE_CANTONS:
            assert len(canton) == 2, f"Canton code '{canton}' is not 2 letters"
            assert canton.isalpha(), f"Canton code '{canton}' is not alphabetic"
            assert canton.isupper(), f"Canton code '{canton}' is not uppercase"

    def test_expected_cantons_present(self):
        expected = {"GE", "VD", "VS", "NE", "JU", "FR"}
        assert config.ROMANDIE_CANTONS == expected


# T1.3 - is_allowed() returns False for disallowed URL (synthetic robots.txt, no network)
class TestT1_3_RobotsDisallowed:
    def test_disallowed_url_returns_false(self):
        clear_cache()

        mock_parser = MagicMock(spec=RobotFileParser)
        mock_parser.can_fetch.return_value = False

        with patch("job_scraper.robots._get_parser", return_value=mock_parser):
            result = is_allowed("https://example.com/private/page")

        assert result is False
        mock_parser.can_fetch.assert_called_once()


# T1.4 - is_allowed() returns True when no restriction applies
class TestT1_4_RobotsAllowed:
    def test_allowed_url_returns_true(self):
        clear_cache()

        mock_parser = MagicMock(spec=RobotFileParser)
        mock_parser.can_fetch.return_value = True

        with patch("job_scraper.robots._get_parser", return_value=mock_parser):
            result = is_allowed("https://example.com/jobs/123")

        assert result is True
        mock_parser.can_fetch.assert_called_once()


# T1.5 - User-agent list is non-empty with realistic entries
class TestT1_5_UserAgents:
    def test_user_agents_non_empty(self):
        assert len(config.USER_AGENTS) > 0

    def test_user_agents_are_realistic(self):
        for ua in config.USER_AGENTS:
            assert isinstance(ua, str)
            assert len(ua) > 20, f"User-agent too short to be realistic: '{ua}'"
            assert "Mozilla" in ua, f"User-agent doesn't look realistic: '{ua}'"
