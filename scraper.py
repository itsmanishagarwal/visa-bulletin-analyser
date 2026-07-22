"""Parse bulletin HTML into priority-date records.

Fetching lives nowhere in this project any more: travel.state.gov went behind a
Cloudflare bot challenge in July 2026 that 403s every non-browser client. The
former `fetch_bulletin_page` / `check_latest_bulletin` / `get_bulletin_url`
helpers were removed along with the `requests` dependency — recover them from
git history if that block is ever lifted. Bulletins are now saved by hand; see
README.md.
"""

import re
import unicodedata
from datetime import datetime

from bs4 import BeautifulSoup


def _clean_text(raw):
    """Normalize unicode, collapse all whitespace/hyphens, strip."""
    # Replace non-breaking spaces and other unicode whitespace with regular space
    s = unicodedata.normalize("NFKD", raw)
    # Collapse all whitespace (including \xa0) into single space
    s = re.sub(r"\s+", " ", s)
    # Remove soft hyphens
    s = s.replace("\u00ad", "")
    return s.strip()


def parse_date(date_str):
    """Convert date strings: '01FEB23' → '2023-02-01', 'C' → 'C', 'U' → 'U'."""
    s = _clean_text(date_str).upper()
    if s in ("C", "CURRENT"):
        return "C"
    if s in ("U", "UNAVAILABLE"):
        return "U"
    # Try DDMONYY format
    try:
        dt = datetime.strptime(s, "%d%b%y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
    # Try DDMONYYYY format
    try:
        dt = datetime.strptime(s, "%d%b%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
    return s


def normalize_country(raw):
    """Normalize country header text to canonical names."""
    cleaned = _clean_text(raw)
    # Remove hyphens that break words (e.g., "PHILIP-PINES" → "PHILIPPINES")
    dehyphenated = re.sub(r"(\w)-\s*(\w)", r"\1\2", cleaned)
    lowered = dehyphenated.lower()

    # Parenthesised deliberately: "all chargeability areas" (no "except") is
    # matched by the first clause alone, so both are load-bearing.
    if "chargeability" in lowered or ("charge" in lowered and "except" in lowered):
        return "All Chargeability Areas"
    if "china" in lowered:
        return "China"
    if "india" in lowered:
        return "India"
    if "mexico" in lowered:
        return "Mexico"
    if "philip" in lowered:
        return "Philippines"

    # Handle abbreviated column headers from older bulletins
    abbrev = cleaned.upper().strip()
    abbrev_map = {
        "CH": "China",
        "IN": "India",
        "ME": "Mexico",
        "MX": "Mexico",
        "PH": "Philippines",
    }
    if abbrev in abbrev_map:
        return abbrev_map[abbrev]

    # Skip unrecognized countries — only keep the 5 canonical ones
    return None


def normalize_category(raw, visa_type):
    """Normalize category names to canonical forms."""
    cleaned = _clean_text(raw)
    # Remove trailing asterisks and other annotations
    cleaned = re.sub(r"\*+$", "", cleaned).strip()
    # Remove hyphens breaking words
    dehyphenated = re.sub(r"(\w)-\s*(\w)", r"\1\2", cleaned)
    lowered = dehyphenated.lower()
    # Multi-word labels are matched against a squashed form so that spacing can
    # never decide the outcome. _clean_text strips soft hyphens, which turns
    # "Other\xadWorkers" into "OtherWorkers" — that lost space previously made
    # `"other worker" in lowered` fail, and the label fell through to the
    # catch-all as a bogus "OtherWorkers" category for 24 months of bulletins.
    squashed = re.sub(r"[^a-z0-9]", "", lowered)

    if visa_type == "family":
        # Normalize all family category variants
        if lowered in ("f1", "1st", "1st preference"):
            return "F1"
        if lowered in ("f2a", "2a"):
            return "F2A"
        if lowered in ("f2b", "2b"):
            return "F2B"
        if lowered in ("f3", "3rd", "3rd preference"):
            return "F3"
        if lowered in ("f4", "4th", "4th preference"):
            return "F4"
        # If it's short and looks like a family code, uppercase it
        if len(cleaned) <= 4:
            return cleaned.upper()
        return cleaned

    # Employment-based
    if lowered in ("1st", "1st preference"):
        return "EB-1"
    if lowered in ("2nd", "2nd preference"):
        return "EB-2"
    if lowered in ("3rd", "3rd preference"):
        return "EB-3"
    if "otherworker" in squashed:
        return "EB-3 Other Workers"
    if lowered in ("4th", "4th preference"):
        return "EB-4"
    # Single test: "religiousworker" already implies both words are present, so
    # the old `"religious worker" in lowered or ...` first operand was dead.
    if "religiousworker" in squashed:
        return "EB-4 Religious Workers"

    # EB-5 variants
    if "5th" in squashed or "fifth" in squashed:
        if "unreserved" in squashed:
            return "EB-5 Unreserved"
        if "rural" in squashed:
            return "EB-5 Rural"
        if "highunemployment" in squashed:
            return "EB-5 High Unemployment"
        if "infrastructure" in squashed:
            return "EB-5 Infrastructure"
        if "targeted" in squashed or "regional" in squashed:
            return "EB-5 Targeted"
        return "EB-5"

    # Older bulletin categories that should map to EB-5
    if "targeted" in squashed and "employment" in squashed:
        return "EB-5 Targeted"

    # Schedule A, Iraqi/Afghani translators — skip these non-standard categories
    if "schedulea" in squashed:
        return "Schedule A Workers"
    if "iraqi" in squashed or "afghani" in squashed or "translator" in squashed:
        return "Iraqi/Afghani Translators"

    return cleaned


def _identify_table_by_header(header_text):
    """Identify visa_type from the first cell of the header row."""
    h = _clean_text(header_text).lower()
    if "family" in h:
        return "family"
    if "employment" in h:
        return "employment"
    return None


def parse_bulletin(html):
    """Parse all 4 tables from a bulletin HTML page.

    Strategy: identify tables by their first header cell content
    ("Family-Sponsored" or "Employment-based"). The first occurrence of each
    type is Final Action, the second is Filing.

    Returns list of dicts with keys: table_type, visa_type, category, country, priority_date
    """
    soup = BeautifulSoup(html, "html.parser")
    records = []

    seen_count = {"family": 0, "employment": 0}

    tables = soup.find_all("table")

    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        header_cells = rows[0].find_all(["th", "td"])
        if not header_cells:
            continue

        first_header = header_cells[0].get_text(strip=True)
        visa_type = _identify_table_by_header(first_header)
        if visa_type is None:
            continue

        seen_count[visa_type] += 1
        table_type = "final_action" if seen_count[visa_type] == 1 else "filing"

        # Parse country headers (skip first column), track valid column indices
        country_cols = []  # list of (column_index, country_name)
        for i, cell in enumerate(header_cells[1:]):
            country = normalize_country(cell.get_text(strip=True))
            if country:
                country_cols.append((i, country))

        if not country_cols:
            continue

        for row in rows[1:]:
            cells = row.find_all(["th", "td"])
            if len(cells) < 2:
                continue

            raw_category = cells[0].get_text(strip=True)
            if not raw_category:
                continue

            category = normalize_category(raw_category, visa_type)

            for col_idx, country in country_cols:
                if col_idx >= len(cells) - 1:
                    break
                date_text = cells[col_idx + 1].get_text(strip=True)
                if not date_text:
                    continue
                priority_date = parse_date(date_text)
                records.append({
                    "table_type": table_type,
                    "visa_type": visa_type,
                    "category": category,
                    "country": country,
                    "priority_date": priority_date,
                })

    return records
