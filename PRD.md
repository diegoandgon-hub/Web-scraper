# Job Scraper PRD

## 1. Overview

**Project**: Web scraper to find entry-level engineering positions in French-speaking Switzerland (Romandie).

**Problem**: Manually searching for English-only, entry-level process/automation/energy engineering jobs across Swiss job boards and company career pages is time-consuming and error-prone.

**Solution**: An automated CLI tool that scrapes multiple sources, applies multi-layer filtering (keyword + LLM fallback), deduplicates results, and exports clean data.

## 2. Target Job Criteria

### Engineering Disciplines
- Process Engineering
- Automation Engineering
- Energy Engineering

### Geographic Scope
- **Region**: French-speaking Switzerland (Romandie)
- **Cantons**: Geneva (GE), Vaud (VD), Valais (VS), Neuchatel (NE), Jura (JU), Fribourg (FR)
- **Major cities**: Geneva, Lausanne, Sion, Neuchatel, Fribourg, Yverdon, Montreux, Nyon

### Language Requirements
- **MANDATORY**: Position must be fully in English
- **DISCARD IF**: Job requires French or German language skills

### Experience Level
- Entry-level (0-2 years)
- Recent graduates
- Internships NOT requiring current university enrollment
- Trainee/graduate programs

## 3. Tech Stack

| Component | Choice |
|-----------|--------|
| Language | Python 3.11+ |
| Storage | SQLite + CSV/JSON export |
| Testing | pytest + pytest-cov |
| HTTP | requests + BeautifulSoup4 + lxml |
| RSS | feedparser |
| LLM fallback | anthropic (Claude API) |
| Execution | Manual CLI (argparse) |

### Dependencies
```
requests
beautifulsoup4
lxml
feedparser
anthropic
pytest
pytest-cov
```

## 4. Data Sources (Phase 1)

| Source | Method | Notes |
|--------|--------|-------|
| LinkedIn | Public/RSS feeds | No login, public job pages only |
| ABB | Career page scraping | Pilot company (large corp) |
| SICPA | Career page scraping | Pilot company (Lausanne-based) |
| Alpiq | Career page scraping | Pilot company (energy sector) |

## 5. Directory Structure

```
job_scraper/
  __init__.py
  config.py                    # Central configuration
  logging_config.py            # Logging setup
  cli.py                       # CLI entry point
  db/
    __init__.py
    models.py                  # SQLite schema + init_db()
    crud.py                    # CRUD operations
  scrapers/
    __init__.py
    base.py                    # Abstract BaseScraper
    linkedin.py                # LinkedIn RSS/public scraper
    career_pages/
      __init__.py
      abb.py
      sicpa.py
      alpiq.py
  filters/
    __init__.py
    keyword_filter.py          # Rule-based filtering
    llm_filter.py              # Claude API fallback
  export/
    __init__.py
    csv_export.py
    json_export.py
  dedup/
    __init__.py
    deduplicator.py            # Content hash dedup
tests/
  conftest.py
  fixtures/                    # Saved HTML/XML for offline tests
  test_config.py
  test_db.py
  test_base_scraper.py
  test_linkedin_scraper.py
  test_career_scrapers.py
  test_keyword_filter.py
  test_llm_filter.py
  test_export.py
  test_dedup.py
  test_cli.py
  test_integration.py
```

## 6. Database Schema

Table: `jobs`

| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| title | TEXT | NOT NULL |
| company | TEXT | NOT NULL |
| location_city | TEXT | |
| location_canton | TEXT | GE, VD, VS, NE, JU, FR |
| description | TEXT | |
| qualifications | TEXT | |
| language_requirements | TEXT | |
| experience_level | TEXT | |
| deadline | TEXT | ISO date or NULL |
| url | TEXT | NOT NULL, UNIQUE |
| date_posted | TEXT | ISO date |
| date_scraped | TEXT | NOT NULL, ISO datetime |
| source | TEXT | NOT NULL |
| filter_status | TEXT | DEFAULT 'unprocessed' |
| filter_reason | TEXT | |
| content_hash | TEXT | SHA-256 for dedup |

## 7. CLI Interface

```bash
python -m job_scraper init                          # Create DB + output dir
python -m job_scraper scrape --all                  # Run all scrapers
python -m job_scraper scrape --source linkedin      # Run specific scraper
python -m job_scraper filter                        # Keyword filter only
python -m job_scraper filter --llm                  # Keyword + LLM fallback
python -m job_scraper export --format csv           # Export passed jobs
python -m job_scraper export --format json --status all
python -m job_scraper status                        # DB summary
```

## 8. Filtering Logic

### Layer 1: Keyword Filter
1. **Geographic**: location_canton must be in Romandie cantons
2. **Language**: scan description/qualifications for French/German requirement patterns -> reject
3. **Experience**: check for entry-level/graduate/intern patterns, reject senior/5+ years
4. **Discipline**: at least one process/automation/energy keyword in title or description
5. **Enrollment**: reject internships requiring active university enrollment

**Outcomes**: `passed`, `rejected` (with reason), or `ambiguous`

### Layer 2: LLM Fallback (Claude API)
- Only invoked for `ambiguous` jobs (when `--llm` flag is used)
- Structured prompt asking Claude to evaluate language, experience, and discipline fit
- Description truncated to 2000 chars
- API errors leave status as `ambiguous`

---

## 9. Task Breakdown (Task → Feature → Test)

---

### TASK 1: Project Setup & Configuration

**Features:**
- **F1.1** Repository scaffolding: directory structure, `pyproject.toml`, `.gitignore`, `requirements.txt`
- **F1.2** Central config module (`config.py`):
  - DATABASE_PATH, OUTPUT_DIR
  - ROMANDIE_CANTONS, ROMANDIE_CITIES
  - TARGET_KEYWORDS (per discipline)
  - LANGUAGE_EXCLUDE_PATTERNS, ENTRY_LEVEL_PATTERNS, ENROLLMENT_EXCLUDE_PATTERNS
  - REQUEST_DELAY_SECONDS, USER_AGENTS
  - CLAUDE_API_KEY (env var), CLAUDE_MODEL, LOG_LEVEL
- **F1.3** robots.txt compliance: `is_allowed(url)` using `urllib.robotparser` with caching

**Tests:**
| ID | Description |
|----|-------------|
| T1.1 | Config loads all expected keys; missing Claude key only errors when LLM filter is invoked |
| T1.2 | ROMANDIE_CANTONS has exactly 6 two-letter codes |
| T1.3 | `is_allowed()` returns False for disallowed URL (synthetic robots.txt, no network) |
| T1.4 | `is_allowed()` returns True when no restriction applies |
| T1.5 | User-agent list is non-empty with realistic entries |

---

### TASK 2: Database Layer

**Features:**
- **F2.1** SQLite schema (`models.py`): `jobs` table as defined in section 6, `init_db()` creates table idempotently
- **F2.2** CRUD operations (`crud.py`):
  - `insert_job(job_dict) -> int | None`
  - `job_exists(url: str) -> bool`
  - `get_jobs(filter_status=None, source=None) -> list[dict]`
  - `update_filter_status(job_id, status, reason)`
  - `get_all_content_hashes() -> set[str]`
  - `count_jobs(filter_status=None) -> int`

**Tests:**
| ID | Description |
|----|-------------|
| T2.1 | `init_db()` creates table; calling twice doesn't error |
| T2.2 | `insert_job()` returns valid id |
| T2.3 | Duplicate URL insert handled gracefully (returns None or skips) |
| T2.4 | `job_exists()` returns correct bool |
| T2.5 | `get_jobs(filter_status="passed")` returns only matching rows |
| T2.6 | `update_filter_status()` changes the correct row |
| T2.7 | `count_jobs()` returns accurate count |
| T2.8 | All tests use in-memory SQLite (`:memory:`) |

---

### TASK 3: Core Scraping Engine

**Features:**
- **F3.1** Abstract `BaseScraper` class (`scrapers/base.py`):
  - `__init__(source_name)`: creates `requests.Session` with random user-agent
  - `fetch(url)`: robots.txt check, configurable delay, 30s timeout, 3 retries on 429/5xx with exponential backoff
  - `parse(response)`: abstract method
  - `scrape()`: template method calling fetch then parse
- **F3.2** Custom exceptions: `ScrapingError`, `ParseError`
- **F3.3** Session management: rotates user-agents per request, respects delay between same-domain calls

**Tests:**
| ID | Description |
|----|-------------|
| T3.1 | BaseScraper cannot be instantiated directly (abstract) |
| T3.2 | Concrete subclass `fetch()` returns Response (mocked requests.get) |
| T3.3 | Retry on 429, succeeds on second attempt |
| T3.4 | `ScrapingError` raised after 3 consecutive 5xx |
| T3.5 | URL skipped when robots.txt disallows |
| T3.6 | Delay between calls respected (mock time.sleep) |
| T3.7 | User-agent rotates between consecutive calls |

---

### TASK 4: LinkedIn Public Scraper

**Features:**
- **F4.1** RSS feed scraper (`scrapers/linkedin.py`): constructs feed URLs per keyword+city, uses `feedparser`, extracts title/company/location/URL/date_posted
- **F4.2** Public job page parser: fetches `/jobs/view/<id>` for full description, qualifications, experience level, language requirements. Handles login-wall gracefully (keeps partial data, logs warning)
- **F4.3** Search query generation: one query per (keyword group x city), deduplicates results by URL

**Tests:**
| ID | Description |
|----|-------------|
| T4.1 | RSS XML fixture parsed into correct dicts with expected keys |
| T4.2 | Cross-query URL deduplication works |
| T4.3 | Job page HTML fixture parsed for all fields |
| T4.4 | Login-wall HTML results in partial data + warning log |
| T4.5 | Query URLs correctly constructed with proper encoding |
| T4.6 | All tests use fixtures, zero network calls |

---

### TASK 5: Company Career Page Scrapers (ABB, SICPA, Alpiq)

**Features (per company X):**
- **F5.X.1** Page fetching + pagination for career listings
- **F5.X.2** Job detail parsing: extract all data fields (title, company, location, description, qualifications, language requirements, experience level, deadline, date posted)
- **F5.X.3** Location normalization: map company's format to canonical `(city, canton)` using Swiss city-to-canton lookup table

**Tests (per company X):**
| ID | Description |
|----|-------------|
| T5.X.1 | Listing page HTML fixture parsed to extract job URLs |
| T5.X.2 | Detail page HTML fixture parsed for all required fields |
| T5.X.3 | Pagination across multiple pages works |
| T5.X.4 | "Lausanne, Switzerland" normalizes to ("Lausanne", "VD") |
| T5.X.5 | "Zurich, Switzerland" correctly identified as NOT Romandie, job skipped |
| T5.X.6 | Missing fields result in None, not crashes |

**Build order**: ABB → SICPA → Alpiq (each built and tested independently)

---

### TASK 6: Filtering Engine

**Features:**
- **F6.1** Keyword filter (`filters/keyword_filter.py`): applies all 5 filter checks (geographic, language, experience, discipline, enrollment). Returns `(status, reason)` tuple
- **F6.2** Ambiguity detection: marks jobs `ambiguous` when language requirement unclear, experience level missing, or description too short
- **F6.3** LLM filter fallback (`filters/llm_filter.py`): sends ambiguous jobs to Claude API with structured prompt, expects JSON `{pass: bool, reason: str}`, truncates description to 2000 chars, handles API errors gracefully
- **F6.4** Filter pipeline: `run_filters(db)` processes all `unprocessed` jobs through keyword filter, then LLM for ambiguous. Updates DB, returns summary `{passed: N, rejected: N, ambiguous: N}`

**Tests:**
| ID | Description |
|----|-------------|
| T6.1 | English process engineer job in Geneva passes all filters |
| T6.2 | Zurich job rejected ("location not in Romandie") |
| T6.3 | "Francais courant requis" in description -> rejected |
| T6.4 | "German: fluent" in qualifications -> rejected |
| T6.5 | "5+ years experience" -> rejected (not entry-level) |
| T6.6 | "Currently enrolled student" internship -> rejected |
| T6.7 | No language requirements + short description -> ambiguous |
| T6.8 | Matching title but no experience info -> ambiguous |
| T6.9 | LLM filter returns pass -> status becomes "passed" (mocked API) |
| T6.10 | LLM filter returns reject -> status becomes "rejected" (mocked API) |
| T6.11 | LLM filter API error -> status stays "ambiguous", error logged |
| T6.12 | Description truncated to 2000 chars before LLM call |
| T6.13 | Pipeline: 3 jobs (pass, reject, ambiguous->LLM) verified in DB |
| T6.14 | City "Lausanne" resolves to canton "VD" when canton is missing |

---

### TASK 7: Data Export

**Features:**
- **F7.1** CSV export (`export/csv_export.py`): `export_csv(db, output_path, filter_status="passed")`, proper quoting, default filename `jobs_passed_YYYY-MM-DD.csv`
- **F7.2** JSON export (`export/json_export.py`): `export_json(db, output_path, filter_status="passed")`, pretty-printed, default filename `jobs_passed_YYYY-MM-DD.json`
- **F7.3** Export metadata: `export_date`, `total_count`, `filter_status` included in both formats

**Tests:**
| ID | Description |
|----|-------------|
| T7.1 | CSV has correct row count + header + metadata comments |
| T7.2 | CSV handles commas/newlines in descriptions |
| T7.3 | JSON is valid with correct `metadata.total_count` |
| T7.4 | Export with `filter_status="passed"` excludes rejected jobs |
| T7.5 | Non-existent output directory raises clear error |
| T7.6 | Default filename contains today's date |

---

### TASK 8: CLI Interface

**Features:**
- **F8.1** CLI entry point (`cli.py`) with argparse subcommands: `init`, `scrape`, `filter`, `export`, `status`
- **F8.2** `scrape [--source SOURCE | --all]`: runs specific or all scrapers, prints progress
- **F8.3** `filter [--llm]`: keyword filter + optional LLM fallback, prints summary
- **F8.4** `export [--format csv|json] [--status passed|rejected|ambiguous|all] [--output PATH]`
- **F8.5** `status`: prints DB summary (counts by filter_status, by source, last scrape date)
- **F8.6** `init`: creates DB and `output/` directory, idempotent

**Tests:**
| ID | Description |
|----|-------------|
| T8.1 | `init` creates database file at configured path |
| T8.2 | `scrape --source linkedin` calls LinkedInScraper (mocked) |
| T8.3 | `scrape --all` calls all registered scrapers |
| T8.4 | `filter` without `--llm` does not instantiate LLMFilter |
| T8.5 | `filter --llm` processes ambiguous jobs through LLMFilter |
| T8.6 | `export --format json --status all` produces correct output |
| T8.7 | `status` prints correct counts |
| T8.8 | Unknown command prints help and exits with code 1 |

---

### TASK 9: Duplicate Detection

**Features:**
- **F9.1** Content hash dedup (`dedup/deduplicator.py`): SHA-256 of `normalize(title) + normalize(company) + normalize(description[:500])`. Normalization: lowercase, strip whitespace, remove punctuation
- **F9.2** URL dedup: handled by UNIQUE constraint on `url` column
- **F9.3** Cross-source dedup: same job on LinkedIn + career page (different URLs, same content) caught by content hash
- **F9.4** Integration: check URL first (fast), then content hash before DB insert, log skipped duplicates

**Tests:**
| ID | Description |
|----|-------------|
| T9.1 | Identical jobs produce same hash |
| T9.2 | Different titles produce different hashes |
| T9.3 | Minor whitespace differences produce same hash (normalization) |
| T9.4 | `is_duplicate()` returns True when hash in existing set |
| T9.5 | Cross-source duplicate detected (same content, different URLs) |
| T9.6 | URL duplicate caught at DB insert level |

---

### TASK 10: Logging & Error Handling

**Features:**
- **F10.1** Logging config (`logging_config.py`): console handler (INFO, concise) + rotating file handler (`logs/scraper.log`, DEBUG, 5MB, 3 backups)
- **F10.2** Error handling: `ScrapingError`/`ParseError` per-scraper isolation, top-level exception catch in CLI (never raw tracebacks)
- **F10.3** Scrape run summary: sources succeeded/failed, new jobs found, duplicates skipped

**Tests:**
| ID | Description |
|----|-------------|
| T10.1 | Log file created at configured path |
| T10.2 | One scraper error doesn't block others from running |
| T10.3 | ParseError for one job doesn't block other jobs in same scraper |
| T10.4 | Summary correctly counts successes, failures, duplicates |
| T10.5 | Console output at INFO doesn't include DEBUG messages |

---

### TASK 11: Integration & E2E Testing

**Features:**
- **F11.1** Full pipeline test: init DB -> mock scrape (LinkedIn + ABB with 1 overlapping job) -> keyword filter -> LLM filter (mocked) -> CSV export -> verify output
- **F11.2** Filter accuracy test: 20 curated job dicts covering all edge cases, verify each produces expected outcome
- **F11.3** Idempotency test: run same scrape data twice, verify no duplicates

**Tests:**
| ID | Description |
|----|-------------|
| T11.1 | Full pipeline produces correct CSV with expected row count |
| T11.2 | 20 curated jobs all produce expected filter outcomes |
| T11.3 | Double scrape = no duplicate rows in DB |
| T11.4 | Empty scrape result (0 jobs) causes no downstream errors |
| T11.5 | DB state after full pipeline has correct counts per filter_status |

---

## 10. Implementation Phases

| Phase | Tasks | Depends On |
|-------|-------|-----------|
| 1 | Task 1 (Setup) + Task 2 (DB) | Nothing |
| 2 | Task 3 (Base scraper) + Task 9 (Dedup) + Task 10 (Logging) | Phase 1 |
| 3 | Task 4 (LinkedIn) + Task 5: ABB | Phase 2 |
| 4 | Task 6 (Filters) | Phase 1 |
| 5 | Task 7 (Export) + Task 8 (CLI) | Phase 1 + Phase 4 |
| 6 | Task 5: SICPA + Alpiq | Phase 2 |
| 7 | Task 11 (Integration tests) | All above |

## 11. Compliance

- Respect `robots.txt` for all scraped domains
- Terms of service awareness (no login-required scraping)
- GDPR: collect only publicly available job posting data, no personal data
- Rate limiting: minimum 2-second delay between requests to same domain

## 12. Success Metrics

- Number of relevant jobs found per scrape run
- Filter accuracy: % of passed results that genuinely meet all criteria
- Zero false negatives on language filter (no French/German-required jobs slip through)
- Coverage across all 3 pilot companies + LinkedIn
- All tests passing with >80% code coverage

## 13. Out of Scope (Phase 2)

- Email/Slack notifications for new matches
- Scheduled/cron execution
- Web dashboard
- Additional job boards (jobs.ch, Indeed, Glassdoor)
- University career portals (EPFL, UNIGE)
- ML-based classification beyond Claude API fallback
- Salary range extraction
- Remaining companies (Nestle, Roche, Novartis, Romande Energie)
