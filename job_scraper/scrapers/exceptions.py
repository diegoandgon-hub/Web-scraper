"""Custom exceptions for the scraping engine."""


class ScrapingError(Exception):
    """Raised when a page cannot be fetched after retries."""


class ParseError(Exception):
    """Raised when a fetched page cannot be parsed."""
