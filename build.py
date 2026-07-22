#!/usr/bin/env python3
"""Build script: ingest saved bulletin HTML into data/bulletin_data.json.

data/bulletin_data.json is the source of truth — there is no database. Each
month is added by hand:

    1. Open the new bulletin on travel.state.gov in a browser.
    2. Save the page as data/bulletins/YYYY-MM.html
    3. python build.py --ingest

Bulletins are no longer fetched over the network: travel.state.gov sits behind
a Cloudflare bot challenge that 403s every non-browser client. scraper.py still
contains the fetch helpers in case that lifts, but nothing here calls them.
"""

import argparse
import json
import os
import re
import sys

from pdf_bulletin import parse_bulletin_pdf
from scraper import parse_bulletin

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
JSON_PATH = os.path.join(DATA_DIR, "bulletin_data.json")
HTML_DIR = os.path.join(DATA_DIR, "bulletins")

MONTH_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
SUFFIXES = (".pdf", ".html", ".htm")

# A complete modern bulletin is 4 tables x 15 categories x 5 countries = 150 rows.
# A bare count is a weak guard — dropping a whole table still leaves ~100 rows —
# so `validate_records` checks structure and the count is only a backstop.
MIN_RECORDS = 140
EXPECTED_COUNTRIES = 5
EXPECTED_TABLES = {
    ("final_action", "family"),
    ("filing", "family"),
    ("final_action", "employment"),
    ("filing", "employment"),
}


def load_data():
    """Read bulletin_data.json, or return an empty skeleton if absent."""
    if not os.path.exists(JSON_PATH):
        return {"months": [], "countries": [], "categories": {}, "data": {}}
    with open(JSON_PATH) as f:
        return json.load(f)


def rebuild_indexes(doc):
    """Recompute months/countries/categories from doc['data']."""
    rows = [r for month_rows in doc["data"].values() for r in month_rows]

    doc["months"] = sorted(doc["data"], reverse=True)
    doc["countries"] = sorted({r["co"] for r in rows})
    doc["categories"] = {
        vt: sorted({r["cat"] for r in rows if r["vt"] == vt})
        for vt in ("employment", "family")
    }


def write_data(doc):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(JSON_PATH, "w") as f:
        json.dump(doc, f, separators=(",", ":"))
    size_kb = os.path.getsize(JSON_PATH) / 1024
    total = sum(len(v) for v in doc["data"].values())
    print(f"Wrote {JSON_PATH} — {len(doc['months'])} months, {total} records ({size_kb:.1f} KB)")


def month_from_filename(name):
    """'2026-08.pdf' -> ('2026-08', '.pdf'), or None if it isn't a bulletin file."""
    stem, ext = os.path.splitext(name)
    ext = ext.lower()
    if ext not in SUFFIXES or not MONTH_RE.match(stem):
        return None
    return stem, ext


def validate_records(records):
    """Return a list of structural problems; empty means the parse looks sane.

    Catches the failure mode a record count misses: a parser that silently drops
    a table, a category, or a country column still returns plausible-looking
    data. Every category must carry all 5 countries, and all 4 tables must exist.
    """
    problems = []

    if len(records) < MIN_RECORDS:
        problems.append(f"only {len(records)} records (expected >= {MIN_RECORDS})")

    groups = {}
    for r in records:
        table = (r["table_type"], r["visa_type"])
        groups.setdefault(table, {}).setdefault(r["category"], set()).add(r["country"])

    for table_type, visa_type in sorted(EXPECTED_TABLES - set(groups)):
        problems.append(f"missing table: {table_type}/{visa_type}")

    for (table_type, visa_type), cats in sorted(groups.items()):
        for cat, countries in sorted(cats.items()):
            if len(countries) != EXPECTED_COUNTRIES:
                problems.append(
                    f"{table_type}/{visa_type}/{cat}: {len(countries)} countries "
                    f"(expected {EXPECTED_COUNTRIES})"
                )

    return problems


def parse_file(path, ext):
    """Dispatch to the PDF or HTML parser. Both return the same record shape."""
    if ext == ".pdf":
        return parse_bulletin_pdf(path)
    with open(path, encoding="utf-8", errors="replace") as f:
        return parse_bulletin(f.read())


def ingest(force=False):
    """Parse every data/bulletins/*.html into bulletin_data.json."""
    if not os.path.isdir(HTML_DIR):
        print(f"No bulletin directory at {HTML_DIR} — nothing to ingest.")
        return

    doc = load_data()
    files = sorted(os.listdir(HTML_DIR))
    added, skipped, errors = 0, 0, []

    for name in files:
        parsed = month_from_filename(name)
        if parsed is None:
            if not name.startswith(".") and name != "README.md":
                errors.append(f"{name}: not a YYYY-MM{{.pdf,.html}} filename")
            continue
        month, ext = parsed

        if month in doc["data"] and not force:
            skipped += 1
            print(f"{month} — already present, skipping (use --force to re-parse)")
            continue

        path = os.path.join(HTML_DIR, name)
        try:
            records = parse_file(path, ext)
        except Exception as e:
            errors.append(f"{month}: {e}")
            print(f"{month} — ERROR: {e}")
            continue

        problems = validate_records(records)
        if problems:
            for p in problems:
                errors.append(f"{month}: {p}")
            print(f"{month} — ERROR: failed validation ({len(problems)} problem(s))")
            continue

        doc["data"][month] = [
            {
                "tt": r["table_type"],
                "vt": r["visa_type"],
                "cat": r["category"],
                "co": r["country"],
                "pd": r["priority_date"],
            }
            for r in records
        ]
        added += 1
        print(f"{month} — parsed {len(records)} records")

    if errors:
        print(f"\nFailed on {len(errors)} file(s):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)

    if added:
        rebuild_indexes(doc)
        write_data(doc)
    else:
        print(f"\nNothing new to ingest (skipped {skipped}).")

    # Exit non-zero so a bad file is loud rather than a silently-green run.
    if errors:
        sys.exit(1)


def rebuild():
    """Recompute the derived index fields from data without re-parsing HTML."""
    doc = load_data()
    if not doc["data"]:
        print("bulletin_data.json has no data.", file=sys.stderr)
        sys.exit(1)
    rebuild_indexes(doc)
    write_data(doc)


def main():
    parser = argparse.ArgumentParser(description="Visa Bulletin build tool")
    parser.add_argument("--ingest", action="store_true",
                        help="Parse data/bulletins/*.html into bulletin_data.json")
    parser.add_argument("--force", action="store_true",
                        help="Re-parse months already present in the JSON")
    parser.add_argument("--rebuild", action="store_true",
                        help="Recompute months/countries/categories from existing data")
    args = parser.parse_args()

    if not args.ingest and not args.rebuild:
        parser.print_help()
        sys.exit(1)

    if args.ingest:
        ingest(force=args.force)
    if args.rebuild:
        rebuild()


if __name__ == "__main__":
    main()
