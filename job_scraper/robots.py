"""robots.txt compliance checker with caching."""

import logging
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from job_scraper.config import USER_AGENTS

logger = logging.getLogger(__name__)

_cache: dict[str, RobotFileParser] = {}


def _get_parser(url: str) -> RobotFileParser:
    """Return a cached RobotFileParser for the given URL's domain."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    if robots_url not in _cache:
        parser = RobotFileParser()
        parser.set_url(robots_url)
        try:
            parser.read()
        except Exception:
            logger.warning("Could not fetch robots.txt for %s, allowing by default", parsed.netloc)
            parser.allow_all = True
        _cache[robots_url] = parser

    return _cache[robots_url]


def is_allowed(url: str) -> bool:
    """Check if the URL is allowed to be scraped per robots.txt.

    Uses the first user-agent from config as the identifier.
    Results are cached per domain.
    """
    parser = _get_parser(url)
    user_agent = USER_AGENTS[0]
    allowed = parser.can_fetch(user_agent, url)

    if not allowed:
        logger.info("robots.txt disallows scraping: %s", url)

    return allowed


def clear_cache() -> None:
    """Clear the robots.txt parser cache (useful for testing)."""
    _cache.clear()
