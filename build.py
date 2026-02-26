#!/usr/bin/env python3
"""Build script: scrape visa bulletins into SQLite, export to JSON."""

import argparse
from datetime import date, timedelta
import json
import os
import sys

from database import (
    init_db, bulletin_exists, save_bulletin, get_connection,
)
from scraper import fetch_bulletin_page, parse_bulletin, generate_month_range

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
JSON_PATH = os.path.join(DATA_DIR, "bulletin_data.json")


def scrape(start, end):
    """Scrape bulletins from start to end (YYYY-MM strings) into SQLite."""
    init_db()
    sy, sm = (int(x) for x in start.split("-"))
    ey, em = (int(x) for x in end.split("-"))
    months = list(generate_month_range(sy, sm, ey, em))
    total = len(months)
    imported = 0
    skipped = 0
    errors = []

    for i, (y, m) in enumerate(months, 1):
        month_str = f"{y}-{m:02d}"
        if bulletin_exists(month_str):
            skipped += 1
            print(f"[{i}/{total}] {month_str} — already exists, skipping")
            continue
        try:
            print(f"[{i}/{total}] {month_str} — fetching...")
            html = fetch_bulletin_page(y, m)
            records = parse_bulletin(html)
            if records:
                save_bulletin(month_str, records)
                imported += 1
                print(f"         saved {len(records)} records")
            else:
                errors.append(f"{month_str}: no data parsed")
                print(f"         WARNING: no data parsed")
        except Exception as e:
            errors.append(f"{month_str}: {e}")
            print(f"         ERROR: {e}")

    print(f"\nDone. Imported: {imported}, Skipped: {skipped}, Errors: {len(errors)}")
    if errors:
        for err in errors:
            print(f"  - {err}")


def export():
    """Export SQLite data to a flat JSON file for the static frontend."""
    init_db()
    conn = get_connection()

    # Get all months
    rows = conn.execute(
        "SELECT bulletin_month FROM bulletins ORDER BY bulletin_month DESC"
    ).fetchall()
    months = [r["bulletin_month"] for r in rows]

    if not months:
        print("No data in database. Run --scrape first.")
        conn.close()
        sys.exit(1)

    # Get all countries
    rows = conn.execute(
        "SELECT DISTINCT country FROM priority_dates ORDER BY country"
    ).fetchall()
    countries = [r["country"] for r in rows]

    # Get categories by visa type
    rows = conn.execute(
        "SELECT DISTINCT category FROM priority_dates WHERE visa_type = 'employment' ORDER BY category"
    ).fetchall()
    employment_cats = [r["category"] for r in rows]

    rows = conn.execute(
        "SELECT DISTINCT category FROM priority_dates WHERE visa_type = 'family' ORDER BY category"
    ).fetchall()
    family_cats = [r["category"] for r in rows]

    # Get all priority date records grouped by month
    rows = conn.execute(
        """SELECT b.bulletin_month, pd.table_type, pd.visa_type,
                  pd.category, pd.country, pd.priority_date
           FROM priority_dates pd
           JOIN bulletins b ON pd.bulletin_id = b.id
           ORDER BY b.bulletin_month DESC"""
    ).fetchall()
    conn.close()

    data = {}
    for r in rows:
        month = r["bulletin_month"]
        if month not in data:
            data[month] = []
        data[month].append({
            "tt": r["table_type"],
            "vt": r["visa_type"],
            "cat": r["category"],
            "co": r["country"],
            "pd": r["priority_date"],
        })

    output = {
        "months": months,
        "countries": countries,
        "categories": {
            "employment": employment_cats,
            "family": family_cats,
        },
        "data": data,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(JSON_PATH, "w") as f:
        json.dump(output, f, separators=(",", ":"))

    size_kb = os.path.getsize(JSON_PATH) / 1024
    print(f"Exported {len(months)} months to {JSON_PATH} ({size_kb:.1f} KB)")


def main():
    parser = argparse.ArgumentParser(description="Visa Bulletin build tool")
    parser.add_argument("--scrape", action="store_true", help="Scrape bulletins into SQLite")
    parser.add_argument("--start", default="2006-01", help="Start month (YYYY-MM)")
    next_month = (date.today().replace(day=1) + timedelta(days=32)).strftime("%Y-%m")
    parser.add_argument("--end", default=next_month, help="End month (YYYY-MM)")
    parser.add_argument("--export", action="store_true", help="Export SQLite to JSON")
    args = parser.parse_args()

    if not args.scrape and not args.export:
        parser.print_help()
        sys.exit(1)

    if args.scrape:
        scrape(args.start, args.end)

    if args.export:
        export()


if __name__ == "__main__":
    main()
