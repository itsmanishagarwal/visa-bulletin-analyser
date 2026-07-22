# Visa Bulletin Tracker

A static site that tracks and visualizes U.S. visa bulletin priority dates over time. Data comes from the [U.S. Department of State Visa Bulletin](https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin.html).

## Key Terms

### Table Types

- **Final Action Dates** — The cutoff date for when a visa number is actually available. If your priority date is before this date, you can complete the final step of your green card process (adjustment of status or consular processing).
- **Filing Dates (Dates for Filing)** — An earlier cutoff that lets you submit your application paperwork (I-485) before a visa number is actually available. USCIS announces each month whether filing dates can be used.

### Visa Types

#### Employment-Based

| Category | Description |
|----------|-------------|
| **EB-1** | Priority workers: persons with extraordinary ability, outstanding professors/researchers, multinational executives/managers |
| **EB-2** | Professionals with advanced degrees or exceptional ability |
| **EB-3** | Skilled workers (min. 2 years experience), professionals (bachelor's degree), and other workers |
| **EB-3 Other Workers** | Unskilled workers performing labor for which qualified workers are not available in the U.S. |
| **EB-4** | Special immigrants: religious workers, certain international organization employees, and others |
| **EB-4 Religious Workers** | Ministers and religious workers in a religious vocation |
| **EB-5** | Immigrant investors ($1.05M standard, or $800K in targeted employment areas) |
| **EB-5 Unreserved** | Standard EB-5 not set aside for specific project types |
| **EB-5 Rural** | EB-5 visas reserved for rural area projects |
| **EB-5 High Unemployment** | EB-5 visas reserved for high unemployment area projects |
| **EB-5 Infrastructure** | EB-5 visas reserved for infrastructure projects |

#### Family-Based

| Category | Description |
|----------|-------------|
| **F1** | Unmarried sons and daughters (21+) of U.S. citizens |
| **F2A** | Spouses and children (under 21) of permanent residents |
| **F2B** | Unmarried sons and daughters (21+) of permanent residents |
| **F3** | Married sons and daughters of U.S. citizens |
| **F4** | Brothers and sisters of adult U.S. citizens |

### Other Terms

- **Priority Date** — The date that establishes your place in the visa queue. For employment-based cases, this is typically the date your labor certification (PERM) was filed. For family-based cases, it is the date your petition (I-130) was filed.
- **Country (Chargeability)** — Visa limits are applied per country of birth. Most countries fall under "All Chargeability Areas". Countries with high demand (China, India, Mexico, Philippines) have separate, often longer wait times.
- **Current (C)** — Visa numbers are immediately available. No waiting required.
- **Unavailable (U)** — No visa numbers available in this category.
- **Retrogression** — When a cutoff date moves backward (earlier), meaning longer waits. This happens when demand exceeds supply.
- **Movement** — The change in priority date between two bulletin months, measured in days.

## Data Source

All data comes from the official U.S. Department of State Visa Bulletin page:

https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin.html

Bulletins are published monthly, typically in the middle of the prior month (e.g., the March bulletin is published in mid-February).

`travel.state.gov` sits behind a Cloudflare bot challenge that returns `403` to
every non-browser client, so bulletins are **not** fetched automatically. New
months are added by hand (see below). `scraper.py` still contains the fetch
helpers in case that block is ever lifted, but nothing calls them.

## Data model

`data/bulletin_data.json` is the **source of truth** — a single flat file, the
only thing the browser loads. There is no database.

```
data/bulletins/YYYY-MM.html   saved bulletin pages (build input)
data/bulletin_data.json       source of truth (deployed)
```

## Usage

### Adding a new month

1. Open the new bulletin on travel.state.gov in a browser (it 403s any
   non-browser client, so this step can't be automated).
2. Save it into `data/bulletins/` as either `YYYY-MM.pdf` or `YYYY-MM.html`
   — e.g. `2026-08.pdf`. Both parse to the same records.
3. Ingest and commit:

```bash
pip install -r requirements.txt
python3 build.py --ingest
git add data/ && git commit -m "Add YYYY-MM bulletin" && git push
```

`--ingest` skips months already present (use `--force` to re-parse) and exits
non-zero if any file fails to parse. Pushing to `main` deploys automatically.

**PDF ingest needs `pdftotext`** (poppler), a system binary rather than a pip
package: `brew install poppler` on macOS, `apt install poppler-utils` on Debian.
HTML ingest has no extra dependency.

**Sanity-check every new month.** The PDF parser infers table structure from
text layout, so a layout change could drop or misalign a row without erroring.
Compare against the previous month before committing — every category should be
present, and movements should be plausible:

```bash
python3 - <<'EOF'
import json; d=json.load(open('data/bulletin_data.json'))
a,b = d['months'][1], d['months'][0]
pa={(r['tt'],r['vt'],r['cat'],r['co']):r['pd'] for r in d['data'][a]}
pb={(r['tt'],r['vt'],r['cat'],r['co']):r['pd'] for r in d['data'][b]}
print(f"{a} -> {b}: keys match:", set(pa)==set(pb), "| rows:", len(pa), len(pb))
for k in sorted(set(pa)&set(pb)):
    if pa[k]!=pb[k]: print("  ", "/".join(k), pa[k], "->", pb[k])
EOF
```

### Serve locally

```bash
python3 -m http.server
```

Open http://localhost:8000 in your browser.

### GitHub Pages

The site is built and deployed via GitHub Actions on every push to `main`, and
on manual dispatch. There is no scheduled run — the data only changes when you
commit a new bulletin.
