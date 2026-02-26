# Visa Bulletin Tracker

A static site that tracks and visualizes U.S. visa bulletin priority dates over time. Data is scraped from the [U.S. Department of State Visa Bulletin](https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin.html).

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

All data is scraped from the official U.S. Department of State Visa Bulletin page:

https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin.html

Bulletins are published monthly, typically in the middle of the prior month (e.g., the March bulletin is published in mid-February).

## Usage

### Build locally

```bash
pip install -r requirements.txt

# Scrape bulletins into SQLite
python build.py --scrape --start 2006-01

# Export to JSON for the frontend
python build.py --export

# Serve locally
python -m http.server
```

Open http://localhost:8000 in your browser.

### GitHub Pages

The site is automatically built and deployed via GitHub Actions on every push to `main` and on the 1st of each month.
