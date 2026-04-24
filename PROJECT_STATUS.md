# Project Status

## Current Goal

Build a free-hosted website that shows Seoul apartment record-high trades.

The intended daily output is an image-style report like:

- title: today's Seoul apartment record-high list
- rows: district, exclusive area, apartment name, household count, previous high, deal price, increase
- site should show the generated report immediately
- automation should run every morning at 06:00 KST

## Current Data State

Local SQLite DB exists at:

```text
data/trades.sqlite3
```

As of the last check, it had 448,066 trade rows from 2018-04-01 to 2026-04-23.

Those rows are now marked as baseline/backfill:

```text
is_backfill = 1
first_seen_date = NULL
```

Future daily collection should use `--mode daily`. Newly inserted rows from daily collection get:

```text
is_backfill = 0
first_seen_date = collection date
```

## Important Environment Variables

`.env` should contain:

```env
MOLIT_API_KEY=...
APT_INFO_API_KEY=...
```

The two keys are currently the same. Code also falls back to `MOLIT_API_KEY` if `APT_INFO_API_KEY` is missing.

Do not commit `.env`.

## Main Files

- `collector.py`: downloads apartment trade rows into SQLite. Default range is now 8 years.
- `complex_collector.py`: downloads Seoul apartment complex basic info, including household count.
- `database.py`: creates and writes SQLite tables.
- `records.py`: finds contract-date record highs and newly-seen record highs.
- `complexes.py`: matches trade rows to complex info to get household count.
- `report_image.py`: creates `public/today-record-highs.svg`.
- `build_static_site.py`: creates `public/index.html` and the report SVG.
- `app.py`: local web app at `http://127.0.0.1:8000`.
- `.github/workflows/daily-report.yml`: planned GitHub Actions workflow for free daily report generation and GitHub Pages deploy.

## Commands To Run Locally

Small trade API test:

```powershell
& 'C:\Users\hanjj\AppData\Local\Python\bin\python.exe' collector.py --start 202403 --end 202403 --gu 11680 --sleep 0 --max-failures 1
```

Full 8-year Seoul trade collection:

```powershell
& 'C:\Users\hanjj\AppData\Local\Python\bin\python.exe' collector.py --mode backfill --sleep 0.2
```

Daily refresh for current and previous month:

```powershell
& 'C:\Users\hanjj\AppData\Local\Python\bin\python.exe' collector.py --mode daily --start 202603 --end 202604 --sleep 0.2
```

Preferred daily operation command:

```powershell
& 'C:\Users\hanjj\AppData\Local\Python\bin\python.exe' daily_update.py
```

Show newly-seen record highs:

```powershell
& 'C:\Users\hanjj\AppData\Local\Python\bin\python.exe' show_records.py --seen-date 2026-04-23 --limit 30
```

Small apartment complex info test:

```powershell
& 'C:\Users\hanjj\AppData\Local\Python\bin\python.exe' complex_collector.py --limit 10
```

Full Seoul apartment complex info collection:

```powershell
& 'C:\Users\hanjj\AppData\Local\Python\bin\python.exe' complex_collector.py
```

Build the static report site:

```powershell
& 'C:\Users\hanjj\AppData\Local\Python\bin\python.exe' build_static_site.py
```

Run local web app:

```powershell
& 'C:\Users\hanjj\AppData\Local\Python\bin\python.exe' app.py
```

Open:

```text
http://127.0.0.1:8000
```

## Next Context Prompt

Use this prompt in a new Codex context:

```text
This project is a Seoul apartment record-high trade website.
First read PROJECT_STATUS.md and understand the current state.

Tasks:
1. Continue from the completed 8-year baseline DB.
2. Run complex_collector.py to collect apartment complex basic info, especially household counts.
3. Verify the newly-seen record-high logic in records.py.
4. Verify report_image.py creates a report SVG similar to the user's sample image.
5. Finish the free hosting setup using GitHub Pages and GitHub Actions.
6. Make the report update every day at 06:00 KST using daily mode for current and previous month.

Important:
- .env contains MOLIT_API_KEY and APT_INFO_API_KEY. Never commit it.
- data/trades.sqlite3 should not be committed.
- The Codex tool session may not have API network access. If API calls fail here, guide the user to run the commands in their real local terminal.
```
