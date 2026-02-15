"""F6.3 — LLM filter fallback using Claude API for ambiguous jobs."""

from __future__ import annotations

import json
import logging

import anthropic

from job_scraper.config import CLAUDE_API_KEY, CLAUDE_MODEL, LLM_DESCRIPTION_MAX_CHARS

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a job listing classifier. Determine if this job posting is suitable \
for an entry-level engineer (process, automation, or energy) in \
French-speaking Switzerland who can only work in English.

Respond ONLY with JSON: {"pass": true/false, "reason": "brief explanation"}
"""


def _build_user_prompt(job: dict) -> str:
    """Build the user prompt, truncating description to max chars."""
    desc = (job.get("description") or "")[:LLM_DESCRIPTION_MAX_CHARS]
    return (
        f"Title: {job.get('title', 'N/A')}\n"
        f"Company: {job.get('company', 'N/A')}\n"
        f"Location: {job.get('location_city', 'N/A')}, {job.get('location_canton', 'N/A')}\n"
        f"Description: {desc}\n"
        f"Qualifications: {job.get('qualifications', 'N/A')}\n"
        f"Experience level: {job.get('experience_level', 'N/A')}\n"
        f"Language requirements: {job.get('language_requirements', 'N/A')}\n"
    )


def llm_filter(job: dict) -> tuple[str, str]:
    """Send an ambiguous job to Claude API and return (status, reason).

    Returns:
        ("passed", reason) or ("rejected", reason) based on LLM response.
        ("ambiguous", error_msg) if the API call fails.
    """
    if not CLAUDE_API_KEY:
        logger.warning("No CLAUDE_API_KEY set — skipping LLM filter")
        return "ambiguous", "LLM filter skipped (no API key)"

    try:
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=256,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_user_prompt(job)}],
        )

        response_text = message.content[0].text.strip()
        result = json.loads(response_text)

        if result.get("pass"):
            return "passed", result.get("reason", "LLM approved")
        else:
            return "rejected", result.get("reason", "LLM rejected")

    except json.JSONDecodeError as exc:
        logger.error("LLM returned invalid JSON: %s", exc)
        return "ambiguous", f"LLM response not valid JSON: {exc}"
    except Exception as exc:
        logger.error("LLM filter error: %s", exc)
        return "ambiguous", f"LLM filter error: {exc}"
