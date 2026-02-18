"""F8.1-F8.6 — CLI entry point with argparse subcommands."""

from __future__ import annotations

import argparse
import sys

from job_scraper.config import DATABASE_PATH, OUTPUT_DIR
from job_scraper.db.crud import count_jobs, get_all_content_hashes, get_jobs
from job_scraper.db.models import init_db
from job_scraper.dedup.deduplicator import compute_content_hash, deduplicated_insert
from job_scraper.export.csv_export import export_csv
from job_scraper.export.json_export import export_json
from job_scraper.filters.pipeline import run_filters
from job_scraper.logging_config import setup_logging
from job_scraper.runner import run_scrapers
from job_scraper.scrapers.career_pages.abb import ABBScraper
from job_scraper.scrapers.career_pages.alpiq import AlpiqScraper
from job_scraper.scrapers.career_pages.cern import CERNScraper
from job_scraper.scrapers.career_pages.hitachi import HitachiScraper
from job_scraper.scrapers.career_pages.sicpa import SICPAScraper
from job_scraper.scrapers.jobup import JobUpScraper

_SCRAPERS: dict[str, type] = {
    "jobup": JobUpScraper,
    "abb": ABBScraper,
    "sicpa": SICPAScraper,
    "alpiq": AlpiqScraper,
    "cern": CERNScraper,
    "hitachi": HitachiScraper,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="job-scraper",
        description="Scrape, filter, and export entry-level engineering jobs in Romandie.",
    )
    sub = parser.add_subparsers(dest="command")

    # F8.6 — init
    sub.add_parser("init", help="Create database and output directory")

    # F8.2 — scrape
    scrape_p = sub.add_parser("scrape", help="Run scrapers")
    scrape_group = scrape_p.add_mutually_exclusive_group(required=True)
    scrape_group.add_argument("--source", choices=list(_SCRAPERS.keys()), help="Run a single scraper")
    scrape_group.add_argument("--all", action="store_true", help="Run all scrapers")

    # F8.3 — filter
    filter_p = sub.add_parser("filter", help="Run keyword filter on unprocessed jobs")
    filter_p.add_argument("--llm", action="store_true", help="Send ambiguous jobs to LLM")

    # F8.4 — export
    export_p = sub.add_parser("export", help="Export jobs to CSV or JSON")
    export_p.add_argument("--format", choices=["csv", "json"], default="csv")
    export_p.add_argument(
        "--status",
        choices=["passed", "rejected", "ambiguous", "all", "unprocessed"],
        default="passed",
    )
    export_p.add_argument("--output", default=None, help="Output file path")

    # F8.5 — status
    sub.add_parser("status", help="Print DB summary")

    return parser


# ------------------------------------------------------------------
# Command handlers
# ------------------------------------------------------------------

def cmd_init() -> None:
    """F8.6 — Create DB and output/ directory, idempotent."""
    conn = init_db(str(DATABASE_PATH))
    conn.close()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Database initialized at {DATABASE_PATH}")
    print(f"Output directory ready at {OUTPUT_DIR}")


def cmd_scrape(source: str | None = None, all_sources: bool = False) -> None:
    """F8.2 — Run specific or all scrapers, insert results into DB with dedup."""
    if all_sources:
        scrapers = [cls() for cls in _SCRAPERS.values()]
    else:
        scrapers = [_SCRAPERS[source]()]

    summary = run_scrapers(scrapers)

    # Insert scraped jobs into DB with dedup
    conn = init_db(str(DATABASE_PATH))
    existing_hashes = get_all_content_hashes(conn)
    inserted = 0
    duplicates = 0

    for job_dict in summary.collected_jobs:
        h = compute_content_hash(
            job_dict.get("title", ""),
            job_dict.get("company", ""),
            job_dict.get("description", ""),
        )
        job_dict["content_hash"] = h
        result = deduplicated_insert(conn, job_dict, existing_hashes)
        if result is not None:
            inserted += 1
        else:
            duplicates += 1

    conn.close()
    print(f"Scrape complete: {len(summary.sources_succeeded)} succeeded, "
          f"{len(summary.sources_failed)} failed, "
          f"{inserted} new jobs inserted, {duplicates} duplicates skipped")


def cmd_filter(use_llm: bool = False) -> None:
    """F8.3 — Run keyword filter, optionally with LLM fallback."""
    conn = init_db(str(DATABASE_PATH))
    summary = run_filters(conn, use_llm=use_llm)
    conn.close()
    print(f"Filter complete: {summary['passed']} passed, "
          f"{summary['rejected']} rejected, "
          f"{summary['ambiguous']} ambiguous")


def cmd_export(fmt: str = "csv", status: str = "passed", output: str | None = None) -> None:
    """F8.4 — Export jobs."""
    conn = init_db(str(DATABASE_PATH))
    if status == "all":
        # Export all jobs regardless of filter_status
        # We pass filter_status=None but the export functions expect a string,
        # so we'll get all jobs by fetching each status
        export_fn = export_csv if fmt == "csv" else export_json
        # For "all", we need to handle it differently
        path = _export_all(conn, fmt, output)
    else:
        if fmt == "csv":
            path = export_csv(conn, output, filter_status=status)
        else:
            path = export_json(conn, output, filter_status=status)
    conn.close()
    print(f"Exported to {path}")


def _export_all(conn, fmt: str, output: str | None) -> str:
    """Export all jobs regardless of filter status."""
    from job_scraper.db.crud import get_jobs as _get_jobs
    import csv as _csv
    import json as _json
    from datetime import date
    from pathlib import Path

    jobs = _get_jobs(conn)
    default_name = f"jobs_all_{date.today().isoformat()}.{fmt}"
    path = output or default_name

    parent = Path(path).parent
    if not parent.exists():
        raise FileNotFoundError(f"Output directory does not exist: {parent}")

    if fmt == "csv":
        from job_scraper.export.csv_export import _COLUMNS
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.write(f"# export_date: {date.today().isoformat()}\n")
            f.write(f"# total_count: {len(jobs)}\n")
            f.write(f"# filter_status: all\n")
            writer = _csv.DictWriter(f, fieldnames=_COLUMNS, extrasaction="ignore", quoting=_csv.QUOTE_ALL)
            writer.writeheader()
            for job in jobs:
                writer.writerow(job)
    else:
        payload = {
            "metadata": {
                "export_date": date.today().isoformat(),
                "total_count": len(jobs),
                "filter_status": "all",
            },
            "jobs": jobs,
        }
        with open(path, "w", encoding="utf-8") as f:
            _json.dump(payload, f, indent=2, ensure_ascii=False)

    return path


def cmd_status() -> None:
    """F8.5 — Print DB summary."""
    conn = init_db(str(DATABASE_PATH))
    total = count_jobs(conn)
    passed = count_jobs(conn, filter_status="passed")
    rejected = count_jobs(conn, filter_status="rejected")
    ambiguous = count_jobs(conn, filter_status="ambiguous")
    unprocessed = count_jobs(conn, filter_status="unprocessed")

    # Counts by source
    all_jobs = get_jobs(conn)
    sources: dict[str, int] = {}
    last_scraped: str | None = None
    for job in all_jobs:
        src = job.get("source", "unknown")
        sources[src] = sources.get(src, 0) + 1
        ds = job.get("date_scraped")
        if ds and (last_scraped is None or ds > last_scraped):
            last_scraped = ds

    conn.close()

    print(f"Total jobs: {total}")
    print(f"  Passed: {passed}")
    print(f"  Rejected: {rejected}")
    print(f"  Ambiguous: {ambiguous}")
    print(f"  Unprocessed: {unprocessed}")
    print(f"By source:")
    for src, cnt in sorted(sources.items()):
        print(f"  {src}: {cnt}")
    print(f"Last scraped: {last_scraped or 'N/A'}")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    setup_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    try:
        if args.command == "init":
            cmd_init()
        elif args.command == "scrape":
            cmd_scrape(source=args.source, all_sources=args.all)
        elif args.command == "filter":
            cmd_filter(use_llm=args.llm)
        elif args.command == "export":
            cmd_export(fmt=args.format, status=args.status, output=args.output)
        elif args.command == "status":
            cmd_status()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


def _entry() -> None:
    """Console-script entry point."""
    sys.exit(main())


if __name__ == "__main__":
    _entry()
