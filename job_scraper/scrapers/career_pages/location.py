"""Shared location normalization for career page scrapers (F5.X.3)."""

from __future__ import annotations

from job_scraper.config import ROMANDIE_CANTONS, ROMANDIE_CITIES

# Full canton names to codes (for Workday-style "City, Canton, Country" format)
_CANTON_NAMES = {
    "vaud": "VD",
    "genève": "GE",
    "geneve": "GE",
    "geneva": "GE",
    "valais": "VS",
    "neuchâtel": "NE",
    "neuchatel": "NE",
    "fribourg": "FR",
    "jura": "JU",
}

# Swiss postal code ranges for Romandie cantons (approximate)
_POSTAL_CODE_RANGES: list[tuple[int, int, str]] = [
    (1000, 1099, "VD"),  # Lausanne
    (1100, 1199, "VD"),  # Morges / Cossonay
    (1200, 1299, "GE"),  # Geneva
    (1300, 1399, "VD"),  # Orbe / Vallorbe
    (1400, 1499, "VD"),  # Yverdon
    (1500, 1529, "VD"),  # Villars-Burquin / Grandson
    (1530, 1599, "VD"),  # Payerne area (VD side)
    (1600, 1609, "FR"),  # Châtel-St-Denis area
    (1610, 1699, "FR"),  # Bulle / Oron area
    (1700, 1797, "FR"),  # Fribourg city
    (1800, 1899, "VD"),  # Vevey / Montreux / Aigle
    (1900, 1999, "VS"),  # Martigny / Sion / Sierre
    (2000, 2099, "NE"),  # Neuchâtel
    (2100, 2199, "NE"),  # Boudry / Fleurier
    (2200, 2299, "NE"),  # La Chaux-de-Fonds area
    (2300, 2399, "NE"),  # La Chaux-de-Fonds
    (2400, 2499, "NE"),  # Le Locle
    (2500, 2599, "NE"),  # Biel border area
    (2800, 2899, "JU"),  # Delémont
    (2900, 2999, "JU"),  # Porrentruy
    (3960, 3999, "VS"),  # Upper Valais (Sierre, Visp, Brig)
]


def canton_from_postal_code(postal_code: str) -> str | None:
    """Return the Romandie canton code for a Swiss postal code, or None."""
    try:
        code = int(postal_code.strip())
    except (ValueError, AttributeError):
        return None

    for low, high, canton in _POSTAL_CODE_RANGES:
        if low <= code <= high:
            return canton
    return None


def normalize_location(
    raw_location: str,
    postal_code: str | None = None,
) -> tuple[str | None, str | None]:
    """Map a raw location string to (city, canton).

    Returns (city, canton) if the location is in Romandie, otherwise (None, None).
    The canton is a two-letter code (e.g. "VD").

    Examples:
        "Lausanne, Switzerland"           -> ("Lausanne", "VD")
        "Morges, Vaud, Switzerland"       -> ("Morges", "VD")
        "Zurich, Switzerland"             -> (None, None)
        "Geneva"                          -> ("Geneva", "GE")
        "Crissier" + postal_code="1023"   -> ("Crissier", "VD")
    """
    if not raw_location:
        return None, None

    # Try each known city against the raw string
    for city, canton in ROMANDIE_CITIES.items():
        if city.lower() in raw_location.lower():
            return city, canton

    # Fallback: try canton names in the raw string (e.g. "Morges, Vaud, Switzerland")
    parts = [p.strip() for p in raw_location.split(",")]
    for part in parts:
        canton_code = _CANTON_NAMES.get(part.lower())
        if canton_code and canton_code in ROMANDIE_CANTONS:
            city_name = parts[0] if parts else None
            return city_name, canton_code

    # Fallback: try postal code → canton mapping
    if postal_code:
        canton_code = canton_from_postal_code(postal_code)
        if canton_code and canton_code in ROMANDIE_CANTONS:
            city_name = parts[0] if parts else None
            return city_name, canton_code

    return None, None


def is_romandie(raw_location: str) -> bool:
    """Return True if the raw location maps to a Romandie canton."""
    _, canton = normalize_location(raw_location)
    return canton is not None and canton in ROMANDIE_CANTONS
