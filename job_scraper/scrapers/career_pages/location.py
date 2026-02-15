"""Shared location normalization for career page scrapers (F5.X.3)."""

from __future__ import annotations

from job_scraper.config import ROMANDIE_CANTONS, ROMANDIE_CITIES


def normalize_location(raw_location: str) -> tuple[str | None, str | None]:
    """Map a raw location string to (city, canton).

    Returns (city, canton) if the location is in Romandie, otherwise (None, None).
    The canton is a two-letter code (e.g. "VD").

    Examples:
        "Lausanne, Switzerland" -> ("Lausanne", "VD")
        "Zurich, Switzerland"  -> (None, None)
        "Geneva"               -> ("Geneva", "GE")
    """
    if not raw_location:
        return None, None

    # Try each known city against the raw string
    for city, canton in ROMANDIE_CITIES.items():
        if city.lower() in raw_location.lower():
            return city, canton

    return None, None


def is_romandie(raw_location: str) -> bool:
    """Return True if the raw location maps to a Romandie canton."""
    _, canton = normalize_location(raw_location)
    return canton is not None and canton in ROMANDIE_CANTONS
