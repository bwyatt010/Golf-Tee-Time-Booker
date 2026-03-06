# SoCal Adaptation Guide — Golf Tee Time Sniper Bot

This bot was built for **Austin, TX municipal courses** using the **WebTrac** booking platform. San Diego and Los Angeles use completely different booking platforms, so this is less of a "fix" and more of a **platform rewrite** for the browser automation layer. Everything above that layer (dashboard, scheduling, job management) needs only minor adjustments.

> **Give this file to Claude** (or your AI coding assistant) alongside the codebase and say:
> *"Adapt this bot for [San Diego / Los Angeles] using this guide."*

---

## Quick Summary

| What | Austin (current) | San Diego | Los Angeles |
|---|---|---|---|
| **Platform** | WebTrac (myvscloud.com) | ForeUp (foreupsoftware.com) | EzLinks (golf.lacity.gov) |
| **Timezone** | Central (`America/Chicago`) | Pacific (`America/Los_Angeles`) | Pacific (`America/Los_Angeles`) |
| **Drop time** | Mon 8 PM CT (weekends), 9 AM CT daily (weekdays) | 7 PM PT daily | TBD — verify current policy |
| **Auth type** | Username + password | Email + password | Email + password |
| **Auto-schedule** | Yes — calculates release from target date | Needs updated release formula | Needs updated release formula |
| **Retry on fail** | Yes — stalker checks every 30 min until tee time | Works as-is (just update timezone) | Works as-is (just update timezone) |
| **Courses** | Jimmy Clay, Roy Kizer, Morris Williams, Lions, Hancock | Torrey Pines, Balboa Park, Mission Bay | Rancho Park, Wilson, Harding, Encino, Balboa, Hansen Dam, Woodley Lakes |

---

## File-by-File Changes

### 1. `book_tee_time.py` — The big one (browser automation)

This file contains ALL the WebTrac-specific browser automation. Nearly every selector, URL, and flow step is WebTrac-specific.

#### 1a. Constants & URLs (lines 48-54)

**Current (Austin/WebTrac):**
```python
BASE_URL = "https://txaustinweb.myvscloud.com/webtrac/web"
LOGIN_URL = f"{BASE_URL}/login.html"
SEARCH_URL = f"{BASE_URL}/search.html?display=detail&module=GR&secondarycode={COURSE_CODE}"
CT = ZoneInfo("America/Chicago")
```

**San Diego — replace with:**
```python
BASE_URL = "https://foreupsoftware.com/index.php/booking"
# ForeUp uses a different URL structure — you'll need to inspect the site
# Facility IDs: Torrey Pines=19347, Balboa Park=19348, Mission Bay=19346
# Sub-course IDs: Torrey North=1468, Torrey South=1469
PT = ZoneInfo("America/Los_Angeles")
```

**LA — replace with:**
```python
BASE_URL = "https://golf.lacity.gov"
PT = ZoneInfo("America/Los_Angeles")
```

#### 1b. Drop time logic — `wait_for_drop()` (lines 98-146)

**Current:** Two separate drop times based on weekend vs weekday.
```python
if weekday in (4, 5, 6):  # Friday, Saturday, Sunday
    drop_hour, drop_minute = 20, 0   # 8:00 PM CT
else:
    drop_hour, drop_minute = 9, 0    # 9:00 AM CT
```

**San Diego:** Single daily drop. Replace the entire if/else with:
```python
drop_hour, drop_minute = 19, 0   # 7:00 PM PT daily
drop_label = "7:00:00 PM PT (daily drop)"
```

Also update every `CT` reference in this function to `PT`, and change the log format string from `'%I:%M:%S %p CT'` to `'%I:%M:%S %p PT'` (line 129).

**LA:** Verify the current drop time policy on golf.lacity.gov before setting.

#### 1c. Login flow (lines 317-339)

**Current (WebTrac):**
```python
page.wait_for_selector("#weblogin_username", timeout=15000)
page.fill("#weblogin_username", username)
page.fill("#weblogin_password", password)
page.click("#weblogin_buttonlogin")
```

**San Diego (ForeUp):** You need to reverse-engineer the ForeUp login form. Open https://foreupsoftware.com/index.php/booking in your browser, inspect the login form, and find the correct selectors for email, password, and submit button. ForeUp uses email (not username) for login.

**LA (EzLinks):** Same process — inspect golf.lacity.gov login form for selectors.

#### 1d. Search form interaction (lines 367-397)

**Current (WebTrac):** Uses Vue.js `set_vue_field()` helper to fill date, time, players, holes, then clicks `#grwebsearch_buttonsearch`.

This entire block is WebTrac-specific. ForeUp and EzLinks have completely different search UIs. You'll need to:
1. Navigate to the booking/search page
2. Inspect the form elements (date picker, time selector, player count)
3. Write new selectors for each field
4. Handle any JavaScript frameworks the site uses (React, Vue, vanilla, etc.)

#### 1e. Tee time results parsing (lines 403-433)

**Current:** Parses an HTML `<table>` with `<tr>` rows, extracts time text from table cells.

ForeUp and EzLinks display results differently. You'll need to:
1. Inspect how available tee times are rendered (cards, list items, table rows, etc.)
2. Write new selectors to grab each available time slot
3. Extract the time string and compare against your preferred window

#### 1f. Booking flow — Add to Cart through Checkout (lines 535-635)

**Current (WebTrac):** Clicks "Add to Cart" → Member Selection → Shopping Cart → Checkout → Confirm.

This is the most platform-specific part. Each platform has a different checkout flow:
- **ForeUp:** Typically: select time → choose players → confirm → payment/complete
- **EzLinks:** Different flow — inspect the booking process end-to-end

**Recommendation:** Walk through the entire booking process manually in a non-headless browser first, screenshot each step, note every button/selector, then automate it.

#### 1g. CLI description (line 728)

Change `"Morris Williams Tee Time Sniper Bot"` to your course name.

---

### 2. `dashboard/config.py` — Course definitions

**Current:**
```python
# Austin municipal golf courses — code is the WebTrac secondarycode param
COURSES = {
    "1": "Jimmy Clay",
    "2": "Roy Kizer",
    "3": "Morris Williams",
    "4": "Lions Municipal",
    "5": "Hancock",
}
```

**San Diego — replace with:**
```python
# San Diego municipal courses — key is ForeUp facility_id or course_id
COURSES = {
    "19347-1468": "Torrey Pines North",
    "19347-1469": "Torrey Pines South",
    "19348": "Balboa Park",
    "19346": "Mission Bay",
}
```
Note: the key format depends on how you structure the ForeUp URL params. Adjust to match your booking URL scheme.

**LA — replace with:**
```python
COURSES = {
    "rancho-park": "Rancho Park",
    "wilson": "Wilson",
    "harding": "Harding",
    "encino": "Encino",
    "balboa": "Balboa",
    "hansen-dam": "Hansen Dam",
    "woodley-lakes": "Woodley Lakes",
}
```

---

### 3. `dashboard/runner.py` — Credential key names (lines 22-27)

**Current:**
```python
username = get_setting(db, "webtrac_username") or os.environ.get("WEBTRAC_USERNAME", "")
encoded_pw = get_setting(db, "webtrac_password")
...
password = os.environ.get("WEBTRAC_PASSWORD", "")
```

**Replace `webtrac_username`/`webtrac_password` with:**
- San Diego: `foreup_email` / `foreup_password` and env vars `FOREUP_EMAIL` / `FOREUP_PASSWORD`
- LA: `ezlinks_email` / `ezlinks_password` and env vars `EZLINKS_EMAIL` / `EZLINKS_PASSWORD`

---

### 4. `dashboard/routes/settings.py` — Settings form handler

**Current:** reads/writes `webtrac_username` and `webtrac_password` from form POST and DB.

**Change:** Rename all `webtrac_username` → `foreup_email` (or `ezlinks_email`) and `webtrac_password` → `foreup_password` (or `ezlinks_password`) in both the form field names and the `get_setting`/`set_setting` calls.

---

### 5. `dashboard/routes/schedules.py` — Schedule presets (lines 24-29)

**Current (Austin):**
```python
if preset == "monday_saturday":
    cron_expr = "55 19 * * 1"          # Monday 7:55 PM (server local time)
    description = "Monday 7:55 PM (weekend Fri/Sat/Sun drop)"
elif preset == "daily_weekday":
    cron_expr = "55 8 * * *"           # Daily 8:55 AM
    description = "Daily 8:55 AM (weekday Mon-Thu drop)"
```

**San Diego:** Single daily drop at 7 PM PT. Replace both presets with one:
```python
if preset == "daily_drop":
    cron_expr = "55 18 * * *"          # Daily 6:55 PM PT (5 min before 7 PM drop)
    description = "Daily 6:55 PM (5 min before 7 PM PT drop)"
```
Note: cron uses the server's local timezone. If your server is in PT, use `18 55`. If it's in CT, adjust accordingly (e.g., `55 20` for 8:55 PM CT = 6:55 PM PT).

---

### 6. HTML Templates

#### `dashboard/templates/base.html` (line 38)
```html
<!-- Current -->
Tee Time Sniper &mdash; Austin Municipal Golf
<!-- Change to -->
Tee Time Sniper &mdash; San Diego Municipal Golf
```

#### `dashboard/templates/settings.html`
- Line 7: Change `"Configure your WebTrac credentials"` → `"Configure your ForeUp credentials"` (or EzLinks)
- Line 13-15: Change label from `"Username"` to `"Email"`, change `webtrac_username` to `foreup_email`, change placeholder text
- Line 19-21: Change `webtrac_password` to `foreup_password`, update placeholder text

#### `dashboard/templates/schedules/form.html`
- Line 30: Change `Monday 7:55 PM — Weekend (Fri/Sat/Sun) tee time drop` to `Daily 6:55 PM — nightly tee time drop`
- Line 34: Remove or replace the weekday preset since San Diego has a single daily drop
- Line 46: Update the default cron placeholder from `55 19 * * 1` to `55 18 * * *`

---

### 7. `.env` / `.env.example`

Replace the WebTrac credential block with your platform's credentials. Reference `.env.example.socal` in the repo — it already has a template for both San Diego (ForeUp) and LA (EzLinks) with facility IDs and course codes.

---

## Platform-Specific Research Needed

Before coding, you need to manually inspect the target booking site. For each platform:

1. **Create an account** on the booking platform
2. **Open browser DevTools** (F12) and walk through the entire flow:
   - Login page → note form selectors
   - Navigate to tee time search → note URL structure
   - Fill search form → note field selectors and any JS framework quirks
   - View results → note how time slots are rendered
   - Click a time → note the booking/cart flow
   - Complete checkout → note every confirmation button
3. **Document every CSS selector** you'll need
4. **Note any anti-bot measures** (CAPTCHAs, rate limits, Cloudflare challenges)

### ForeUp (San Diego) Quick Start

ForeUp's booking page is at:
```
https://foreupsoftware.com/index.php/booking/<facility_id>/<course_id>#/teetimes
```
For example, Torrey Pines South:
```
https://foreupsoftware.com/index.php/booking/19347/1469#/teetimes
```

ForeUp also has a **REST API** that returns tee times as JSON — this could be much simpler than scraping HTML. Inspect network requests in DevTools when loading the tee times page.

---

### 8. `dashboard/routes/jobs.py` — Auto-scheduling release time calculation

The bot now auto-schedules jobs when they're created. The release time calculation in `_calculate_release_time()` is Austin-specific:

**Current (Austin):**
```python
CT = ZoneInfo("America/Chicago")

def _calculate_release_time(target_day):
    if weekday in (4, 5, 6):  # Fri, Sat, Sun
        # Weekend drop: Monday before at 8:00 PM CT
        ...
    else:  # Mon, Tue, Wed, Thu
        # Weekday drop: 7 days before at 9:00 AM CT
        ...
```

**San Diego — replace with:**
```python
PT = ZoneInfo("America/Los_Angeles")

def _calculate_release_time(target_day):
    """San Diego: all tee times release 7 days in advance at 7:00 PM PT."""
    target_date = datetime.strptime(target_day, "%Y-%m-%d").date()
    release_date = target_date - timedelta(days=7)
    return datetime(release_date.year, release_date.month, release_date.day,
                    hour=19, minute=0, tzinfo=PT)
```

Also update the `CT` timezone reference throughout the file to `PT`.

---

### 9. `book_tee_time.py` — `cancel_booking()` function

The bot now includes a `cancel_booking(page, target_description_fragment)` function that cancels an existing booking via the WebTrac cancellation flow (history page → "Cancel Item" → checkout → confirm). This is used by the stalker to auto-cancel a fallback booking when it finds a better in-window time.

**This function is entirely WebTrac-specific.** For ForeUp or EzLinks, you'll need to reverse-engineer the cancellation flow on that platform and rewrite `cancel_booking()` with the correct URLs, selectors, and steps.

The matching logic uses a description fragment (e.g. `"2:10 pm, 02/24/2026 on Morris Williams Golf Course"`) to find the right booking in the history table. Other platforms may use confirmation numbers, booking IDs, or different matching strategies.

---

### 10. `dashboard/runner.py` — Stalker schedule, fallback cancellation, and tee time check

The runner creates "stalker" schedules that check for cancellations every 30 minutes after a failed run **or a fallback booking**. When a fallback is booked, the stalker stores the fallback booking description in the schedule and passes `allow_fallback=False` and `cancel_fallback=<description>` to the bot. If the stalker finds an in-window time, the bot books it and auto-cancels the old fallback via `cancel_booking()`.

The `_tee_time_has_passed()` function uses the job's `latest_time` in CT timezone:

**Current (Austin):**
```python
CT = ZoneInfo("America/Chicago")
```

**San Diego — change to:**
```python
PT = ZoneInfo("America/Los_Angeles")
```

Update all `CT` references in `_tee_time_has_passed()` and `_maybe_create_stalker()` to `PT`.

---

## What You Can Keep As-Is

These parts of the codebase are platform-agnostic and need no changes:

- `dashboard/models.py` — SQLite schema for jobs, runs, schedules, settings (including `auto_generated` column)
- `dashboard/scheduler.py` — crontab management
- `dashboard/routes/runs.py` — run history / logs display
- `dashboard/static/` — CSS and JS (purely cosmetic)
- Screenshot capture logic in `book_tee_time.py` — the `screenshot()` helper is generic
- Time window matching logic — `time_in_window()` function is platform-agnostic
- The overall `run_bot()` structure (login → search → parse → book) — just swap the implementation details
- Post-drop retry loop in `book_tee_time.py` — retries every 1s for 5 min after drop (platform-agnostic)
- Stalker/retry schedule logic in `dashboard/runner.py` — auto-creates recurring schedule on failure or fallback (platform-agnostic, just update timezone)
- Fallback-stalker orchestration in `dashboard/runner.py` — `allow_fallback`/`cancel_fallback` config plumbing is platform-agnostic
- Auto-scheduling flow in `dashboard/routes/jobs.py` — calculates release time and creates cron (just update the release time formula and timezone)

---

## LA Warning

LA City Golf (golf.lacity.gov) **explicitly prohibits automated booking / bots** in their Terms of Service. The `.env.example.socal` file includes LA course info for reference only. Proceed at your own risk.
