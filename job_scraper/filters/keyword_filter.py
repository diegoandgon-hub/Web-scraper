"""F6.1 + F6.2 — Keyword filter with 5 checks and ambiguity detection."""

from __future__ import annotations

import re

from job_scraper.config import (
    ENROLLMENT_EXCLUDE_PATTERNS,
    LANGUAGE_EXCLUDE_PATTERNS,
    ROMANDIE_CANTONS,
    ROMANDIE_CITIES,
    SENIOR_EXCLUDE_PATTERNS,
    TARGET_KEYWORDS,
)

# Minimum description length to avoid marking as ambiguous
_MIN_DESCRIPTION_LENGTH = 50


def _matches_any(text: str, patterns: list[str]) -> bool:
    """Return True if *text* matches any of the regex *patterns*."""
    for pattern in patterns:
        if re.search(pattern, text):
            return True
    return False


def _has_discipline_keyword(title: str, description: str) -> bool:
    """Return True if title or description contains a target discipline keyword."""
    combined = (title + " " + description).lower()
    for keywords in TARGET_KEYWORDS.values():
        for kw in keywords:
            if kw.lower() in combined:
                return True
    return False


def _resolve_canton(job: dict) -> str | None:
    """Try to resolve canton from location_canton or location_city."""
    canton = job.get("location_canton")
    if canton:
        return canton
    city = job.get("location_city") or ""
    return ROMANDIE_CITIES.get(city)


def keyword_filter(job: dict) -> tuple[str, str]:
    """Apply all 5 keyword filter checks to a job dict.

    Returns:
        (status, reason) where status is "passed", "rejected", or "ambiguous".
    """
    title = job.get("title") or ""
    description = job.get("description") or ""
    qualifications = job.get("qualifications") or ""
    experience_level = job.get("experience_level") or ""
    text_blob = f"{description} {qualifications}"

    # 1. Geographic — canton must be in Romandie
    canton = _resolve_canton(job)
    if canton and canton not in ROMANDIE_CANTONS:
        return "rejected", f"location not in Romandie (canton={canton})"

    # 2. Language — reject if French/German required
    if _matches_any(text_blob, LANGUAGE_EXCLUDE_PATTERNS):
        return "rejected", "language requirement detected"

    # 3. Experience — reject senior / 5+ years
    if _matches_any(f"{title} {text_blob} {experience_level}", SENIOR_EXCLUDE_PATTERNS):
        return "rejected", "not entry-level (senior/experienced)"

    # 4. Enrollment — reject if requires current enrollment
    if _matches_any(text_blob, ENROLLMENT_EXCLUDE_PATTERNS):
        return "rejected", "requires current enrollment"

    # 5. Discipline — at least one target keyword in title or description
    if not _has_discipline_keyword(title, description):
        return "rejected", "no matching discipline keyword"

    # --- F6.2: Ambiguity detection ---
    # Short or missing description
    if len(description) < _MIN_DESCRIPTION_LENGTH:
        return "ambiguous", "description too short or missing"

    # No experience info at all (no entry-level pattern and no experience_level)
    if not experience_level and not _matches_any(
        text_blob,
        [r"(?i)\bentry[- ]level\b", r"(?i)\bjunior\b", r"(?i)\bgraduate\b",
         r"(?i)\b0[- ]?2\s*years?\b", r"(?i)\b1[- ]?2\s*years?\b",
         r"(?i)\btrainee\b", r"(?i)\bintern(?:ship)?\b"],
    ):
        return "ambiguous", "experience level unclear"

    # No language info at all — could be unclear
    lang_req = job.get("language_requirements") or ""
    if not lang_req and not re.search(r"(?i)\benglish\b", text_blob):
        return "ambiguous", "language requirement unclear"

    return "passed", "all keyword checks passed"
