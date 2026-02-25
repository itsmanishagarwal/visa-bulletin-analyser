import re
import unicodedata
from datetime import datetime

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://travel.state.gov"
BULLETIN_INDEX_URL = f"{BASE_URL}/content/travel/en/legal/visa-law0/visa-bulletin.html"

MONTH_NAMES = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]


def _clean_text(raw):
    """Normalize unicode, collapse all whitespace/hyphens, strip."""
    # Replace non-breaking spaces and other unicode whitespace with regular space
    s = unicodedata.normalize("NFKD", raw)
    # Collapse all whitespace (including \xa0) into single space
    s = re.sub(r"\s+", " ", s)
    # Remove soft hyphens
    s = s.replace("\u00ad", "")
    return s.strip()


def get_fiscal_year(year, month):
    """Federal fiscal year: Oct(10)-Sep(9). Oct 2025 → FY2026."""
    if month >= 10:
        return year + 1
    return year


def get_bulletin_url(year, month):
    """Build the URL for a specific bulletin. year/month are calendar year/month."""
    fy = get_fiscal_year(year, month)
    month_name = MONTH_NAMES[month - 1]
    return (
        f"{BASE_URL}/content/travel/en/legal/visa-law0/visa-bulletin"
        f"/{fy}/visa-bulletin-for-{month_name}-{year}.html"
    )


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

    if "chargeability" in lowered or "charge" in lowered and "except" in lowered:
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

    return cleaned


def normalize_category(raw, visa_type):
    """Normalize category names to canonical forms."""
    cleaned = _clean_text(raw)
    # Remove trailing asterisks and other annotations
    cleaned = re.sub(r"\*+$", "", cleaned).strip()
    # Remove hyphens breaking words
    dehyphenated = re.sub(r"(\w)-\s*(\w)", r"\1\2", cleaned)
    lowered = dehyphenated.lower()

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
    if "other worker" in lowered:
        return "EB-3 Other Workers"
    if lowered in ("4th", "4th preference"):
        return "EB-4"
    if "religious worker" in lowered or "religious" in lowered and "worker" in lowered:
        return "EB-4 Religious Workers"

    # EB-5 variants
    if "5th" in lowered or "fifth" in lowered:
        if "unreserved" in lowered:
            return "EB-5 Unreserved"
        if "rural" in lowered:
            return "EB-5 Rural"
        if "high unemployment" in lowered:
            return "EB-5 High Unemployment"
        if "infrastructure" in lowered:
            return "EB-5 Infrastructure"
        if "targeted" in lowered or "regional" in lowered:
            return "EB-5 Targeted"
        return "EB-5"

    # Older bulletin categories that should map to EB-5
    if "targeted" in lowered and "employment" in lowered:
        return "EB-5 Targeted"

    # Schedule A, Iraqi/Afghani translators — skip these non-standard categories
    if "schedule a" in lowered:
        return "Schedule A Workers"
    if "iraqi" in lowered or "afghani" in lowered or "translator" in lowered:
        return "Iraqi/Afghani Translators"

    return cleaned


def fetch_bulletin_page(year, month):
    """Download HTML for a specific bulletin."""
    url = get_bulletin_url(year, month)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


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

        # Parse country headers (skip first column)
        countries = []
        for cell in header_cells[1:]:
            country = normalize_country(cell.get_text(strip=True))
            if country:
                countries.append(country)

        if not countries:
            continue

        for row in rows[1:]:
            cells = row.find_all(["th", "td"])
            if len(cells) < 2:
                continue

            raw_category = cells[0].get_text(strip=True)
            if not raw_category:
                continue

            category = normalize_category(raw_category, visa_type)

            for i, cell in enumerate(cells[1:]):
                if i >= len(countries):
                    break
                date_text = cell.get_text(strip=True)
                if not date_text:
                    continue
                priority_date = parse_date(date_text)
                records.append({
                    "table_type": table_type,
                    "visa_type": visa_type,
                    "category": category,
                    "country": countries[i],
                    "priority_date": priority_date,
                })

    return records


def check_latest_bulletin():
    """Scrape the main visa bulletin page to find available bulletin months.
    Returns list of (year, month, month_str) tuples for bulletins found on the index page.
    """
    resp = requests.get(BULLETIN_INDEX_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    bulletins = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        match = re.search(
            r"visa-bulletin-for-(\w+)-(\d{4})\.html", href
        )
        if match:
            month_name = match.group(1).lower()
            year = int(match.group(2))
            if month_name in MONTH_NAMES:
                month_num = MONTH_NAMES.index(month_name) + 1
                month_str = f"{year}-{month_num:02d}"
                if (year, month_num, month_str) not in bulletins:
                    bulletins.append((year, month_num, month_str))

    return bulletins


def generate_month_range(start_year, start_month, end_year, end_month):
    """Generate (year, month) tuples from start to end inclusive."""
    y, m = start_year, start_month
    while (y, m) <= (end_year, end_month):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1
