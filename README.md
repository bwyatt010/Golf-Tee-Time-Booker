# ⛳ San Diego Municipal Golf — Tee Time Sniper Bot

Automated tee time booking for San Diego municipal courses via the **ForeUp** platform (foreupsoftware.com).

Tee times open **daily at 7:00 PM PT, 7 days in advance**. This bot logs in before the drop, waits with millisecond precision, and grabs your preferred time the instant they become available.

Supported courses:
- **Torrey Pines North** (facility 19347, course 1468)
- **Torrey Pines South** (facility 19347, course 1469)
- **Balboa Park** (facility 19348)
- **Mission Bay** (facility 19346)

> **⚠️ Before this bot will work**, you must inspect the ForeUp booking site and fill in the correct selectors. See [Manual Inspection Required](#manual-inspection-required) below.

## Features

- **Web dashboard** — create jobs, view runs, manage schedules from a browser UI
- **Auto-scheduling** — create a job with a target date and the bot schedules itself 7 days before at 7 PM PT
- **Precision drop timing** — logs in 5 minutes early, then busy-polls at 50ms precision until the exact release second
- **Post-drop retry loop** — keeps refreshing every 1 second for up to 5 minutes after the drop
- **Cancellation stalking** — automatically checks for cancellations every 30 minutes after a failed run or fallback booking
- **Auto-cancel fallback** — if a fallback was booked and the stalker finds a better time, it books and cancels the old one
- **Multi-course search** — searches courses in priority order, picks the best available slot
- **Fallback booking** — books the closest available time if nothing matches your window, then keeps looking

## Quick Start

### 1. Install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure credentials

```bash
cp .env.example .env
nano .env
```

Fill in `FOREUP_EMAIL` and `FOREUP_PASSWORD` (your ForeUp / San Diego golf account).

### 3. Complete the manual inspection step

See [Manual Inspection Required](#manual-inspection-required) — the bot will not work until you've filled in the ForeUp selectors.

### 4. Launch the dashboard

```bash
python run_dashboard.py
# Opens at http://localhost:5050
```

### 5. Or run the CLI directly

```bash
python book_tee_time.py --no-wait --dry-run   # Quick test (no booking)
python book_tee_time.py                        # Full run — waits for 7 PM PT drop
```

## Configuration

All settings live in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `FOREUP_EMAIL` | — | Your ForeUp account email |
| `FOREUP_PASSWORD` | — | Your ForeUp account password |
| `COURSE_CODE` | `19347-1468` | `facility_id-course_id` (see table below) |
| `COURSE_NAME` | `Torrey Pines North` | Human-readable course name |
| `NUM_PLAYERS` | `2` | Number of players (1–4) |
| `NUM_HOLES` | `18` | 9 or 18 |
| `TARGET_DAY` | `saturday` | Day name or ISO date (YYYY-MM-DD) |
| `EARLIEST_TIME` | `06:00` | Start of preferred window (24hr) |
| `LATEST_TIME` | `08:00` | End of preferred window (24hr) |

### Course codes

| Course | `COURSE_CODE` |
|--------|---------------|
| Torrey Pines North | `19347-1468` |
| Torrey Pines South | `19347-1469` |
| Balboa Park | `19348` |
| Mission Bay | `19346` |

Multi-course: `COURSE_CODE=19347-1468,19347-1469` (first match wins).

## Manual Inspection Required

ForeUp uses a completely different HTML structure from the original Austin/WebTrac system. The following sections in `book_tee_time.py` contain **placeholder selectors marked with `# TODO`** that must be updated before the bot will work:

### 1. Login flow (Step 1)
Open the ForeUp login page in your browser with DevTools (F12) and find the real CSS selectors for the email input, password input, submit button, and a "logged in" indicator.

### 2. Search form (Step 4)
Navigate to your course's booking URL (e.g. `https://foreupsoftware.com/index.php/booking/19347/1469#/teetimes`) and identify the date picker, player count, holes selector, and search button.

**Pro tip:** ForeUp has a REST API. Open DevTools → Network tab while loading the tee times page. JSON responses are far easier to parse than HTML scraping — see `SoCal_Fixes.md` for details.

### 3. Results parsing (Step 5)
Identify how tee time slots are rendered (cards, list, table) and update the selector in the results-scanning block.

### 4. Booking / checkout (Step 7)
Walk through the entire booking process manually, note every button, and implement the ForeUp checkout sequence.

### 5. Cancellation (`cancel_booking()`)
Inspect your ForeUp booking history and implement the cancellation flow in `cancel_booking()`.

## Scheduling

### Auto-scheduling (recommended)
Create a job in the dashboard — it automatically schedules a cron run 5 minutes before the 7 PM PT drop (7 days before the target date).

### Manual cron

```bash
crontab -e
# Daily at 6:55 PM PT (5 min before 7 PM drop)
55 18 * * * cd /path/to/tee-time-bot && /path/to/venv/bin/python book_tee_time.py >> booking.log 2>&1
```

## Troubleshooting

The bot saves screenshots at key steps:

| File | When |
|------|------|
| `debug_login.png` | Login couldn't be confirmed |
| `debug_search_results_<code>.png` | After searching each course |
| `no_times_available.png` | No matching times found |
| `booking_result.png` | Final booking confirmation |
| `debug_timeout.png` | Page load timeout |
| `debug_error.png` | Unexpected error |

**"Missing credentials"** → Set `FOREUP_EMAIL` and `FOREUP_PASSWORD` in `.env`.

**Login fails** → The selectors are placeholders. Inspect the ForeUp login page in DevTools and update Step 1 in `book_tee_time.py`. Check `debug_login.png`.

**No tee times found** → The search form selectors are placeholders. Inspect the ForeUp booking page and update Step 4.

## Notes

- Tee times release **daily at 7:00 PM PT, 7 days in advance** for all San Diego municipal courses.
- You need an account at foreupsoftware.com.
- See `SoCal_Fixes.md` for the full platform adaptation guide, including dashboard file changes.
