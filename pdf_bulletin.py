"""Parse a Visa Bulletin PDF into the same records `scraper.parse_bulletin` returns.

The State Department publishes each bulletin as both HTML and PDF. Since
travel.state.gov went behind a Cloudflare bot challenge (July 2026), the PDF is
the format that's easiest to save by hand, so this is the primary ingest path.

Text is extracted with `pdftotext -layout` (poppler). Two properties of these
PDFs drive the implementation:

1. **Every text line is drawn twice.** The raw extraction contains adjacent
   duplicate lines. They must be collapsed *adjacently* (`uniq`-style) — a
   global "seen" dedup silently deletes legitimate repeated data rows, e.g. the
   three consecutive `C C C C C` rows in the EB-5 set-asides.

2. **Category labels wrap onto lines after their values.** A row renders as
   `Certain  01JAN23 01JAN23 ...` followed by bare `Religious` / `Workers`
   lines. The label must be reassembled before normalizing, because
   `normalize_category("Certain")` returns `"Certain"` rather than
   `"EB-4 Religious Workers"`.

Tables are also split across page breaks (the EB filing table starts on page 5
and finishes on page 6), so rows are collected per *section heading* rather than
per page.
"""

import re
import shutil
import subprocess

from scraper import normalize_category, normalize_country, parse_date

# A cell value: a DDMMMYY date, or the literal C (current) / U (unavailable).
VALUE_RE = re.compile(r"^(?:C|U|\d{2}[A-Z]{3}\d{2})$")

# Column order is fixed across every modern bulletin.
COUNTRIES = [
    "All Chargeability Areas Except Those Listed",
    "CHINA-mainland born",
    "INDIA",
    "MEXICO",
    "PHILIPPINES",
]

# Section headings that introduce each of the four tables, in document order.
SECTIONS = [
    (re.compile(r"final\s+action\s+dates?\s+for\s+family", re.I), "final_action", "family"),
    (re.compile(r"dates?\s+for\s+filing\s+family", re.I), "filing", "family"),
    (re.compile(r"final\s+action\s+dates?\s+for\s+employment", re.I), "final_action", "employment"),
    (re.compile(r"dates?\s+for\s+filing\s+of\s+employment", re.I), "filing", "employment"),
]

# Everything after this heading is the Diversity Visa section — not priority dates.
END_RE = re.compile(r"diversity\s+immigrant\s+\(dv\)\s+category", re.I)

# Parenthetical class-code hints, e.g. "(including C5, T5, I5, R5, NU, RU)".
INCLUDING_RE = re.compile(r"\(\s*including[^)]*\)", re.I)


def pdf_to_lines(path):
    """Run `pdftotext -layout` and collapse adjacent duplicate lines."""
    if shutil.which("pdftotext") is None:
        raise RuntimeError(
            "pdftotext not found — install poppler (macOS: brew install poppler)"
        )
    out = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        check=True, capture_output=True, text=True,
    ).stdout

    lines = []
    for raw in out.splitlines():
        line = raw.rstrip()
        # Adjacent-only dedup: the PDF draws each line twice.
        if lines and line.strip() and line.strip() == lines[-1].strip():
            continue
        lines.append(line)
    return lines


def _split_row(line):
    """Return (label, values) if `line` holds exactly 5 cell values, else None."""
    tokens = line.split()
    values = [t for t in tokens if VALUE_RE.match(t)]
    if len(values) != len(COUNTRIES):
        return None
    # The label is everything before the first value token.
    first = next(i for i, t in enumerate(tokens) if VALUE_RE.match(t))
    label = " ".join(tokens[:first]).strip()
    return label, values


def _clean_label(label):
    return re.sub(r"\s+", " ", INCLUDING_RE.sub("", label)).strip(" :")


def _is_label_fragment(text):
    """Is this a wrapped piece of a category label, rather than body prose?

    Labels wrap into short scraps ("Religious", "Unemployment", "(10%)").
    Prose that follows the last row of a table is long and sentence-like; without
    this guard it would be appended to that row's label and corrupt it.
    """
    words = text.split()
    return len(words) <= 4 and len(text) <= 45 and not text.endswith(".")


def parse_bulletin_pdf(path):
    """Parse a bulletin PDF into records matching `scraper.parse_bulletin`."""
    lines = pdf_to_lines(path)

    records = []
    table = None          # (table_type, visa_type)
    pending = None        # row awaiting label continuation lines

    def flush():
        """Emit the pending row once its wrapped label is complete."""
        if pending is None:
            return
        table_type, visa_type = pending["table"]
        category = normalize_category(_clean_label(pending["label"]), visa_type)
        for country_raw, value in zip(COUNTRIES, pending["values"]):
            records.append({
                "table_type": table_type,
                "visa_type": visa_type,
                "category": category,
                "country": normalize_country(country_raw),
                "priority_date": parse_date(value),
            })

    for line in lines:
        if END_RE.search(line):
            flush()
            pending = None
            table = None
            continue

        heading = next((s for s in SECTIONS if s[0].search(line)), None)
        if heading:
            flush()
            pending = None
            table = (heading[1], heading[2])
            continue

        if table is None:
            continue

        row = _split_row(line)
        if row:
            flush()
            pending = {"table": table, "label": row[0], "values": row[1], "closed": False}
            continue

        # A bare text line directly under a row continues its wrapped label —
        # but only until the first non-label-ish line, after which the label is
        # complete and everything else is body text.
        text = line.strip()
        if pending is None or pending["closed"] or not text:
            continue
        if _is_label_fragment(text):
            pending["label"] += " " + text
        else:
            pending["closed"] = True

    flush()
    return records
