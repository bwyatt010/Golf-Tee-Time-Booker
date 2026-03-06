#!/usr/bin/env python3
"""
San Diego Municipal Golf - Tee Time Sniper Bot
===============================================
Automates booking tee times on San Diego's ForeUp platform (foreupsoftware.com).

Tee times open daily at 7:00 PM PT, 7 days in advance.

Supported courses:
    Torrey Pines North  (facility 19347, schedule 1468)  code: 19347-1468
    Torrey Pines South  (facility 19347, schedule 1469)  code: 19347-1469
    Balboa Park         (facility 19348)                 code: 19348-19348
    Mission Bay         (facility 19346)                 code: 19346-19346

Usage:
    python book_tee_time.py              # Full run — waits for 7 PM PT drop
    python book_tee_time.py --dry-run    # Test mode (no actual booking)
    python book_tee_time.py --no-wait    # Skip the countdown (book immediately)
    python book_tee_time.py --headless   # Run without visible browser
"""

import os
import re
import sys
import time
import argparse
import logging
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

load_dotenv()

USERNAME       = os.getenv("FOREUP_EMAIL", "")
PASSWORD       = os.getenv("FOREUP_PASSWORD", "")
COURSE_NAME    = os.getenv("COURSE_NAME", "Torrey Pines North")
COURSE_CODE    = os.getenv("COURSE_CODE", "19347-1468")
NUM_PLAYERS    = int(os.getenv("NUM_PLAYERS", "2"))
NUM_HOLES      = int(os.getenv("NUM_HOLES", "18"))
TARGET_DAY     = os.getenv("TARGET_DAY", "saturday")
EARLIEST_TIME  = os.getenv("EARLIEST_TIME", "06:00")
LATEST_TIME    = os.getenv("LATEST_TIME",   "08:00")
TWOCAPTCHA_KEY = os.getenv("TWOCAPTCHA_KEY", "")

PT = ZoneInfo("America/Los_Angeles")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("tee-sniper")

DAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def get_target_date(target_day=None):
    if target_day is None:
        target_day = TARGET_DAY
    if len(target_day) == 10 and target_day[4] == "-":
        return datetime.strptime(target_day, "%Y-%m-%d").date()
    target_weekday = DAY_MAP[target_day.lower()]
    today = datetime.now(PT).date()
    days_ahead = (target_weekday - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


def format_date_display(date):
    return date.strftime("%m/%d/%Y")


def wait_for_drop(dry_run=False):
    now    = datetime.now(PT)
    target = now.replace(hour=19, minute=0, second=0, microsecond=0)
    if now >= target:
        log.info("Already past 7:00 PM PT drop. Proceeding immediately.")
        return
    diff = (target - now).total_seconds()
    log.info(f"Current time:   {now.strftime('%I:%M:%S %p PT')}")
    log.info(f"Tee times drop: 7:00:00 PM PT")
    log.info(f"Waiting {diff:.0f}s ({diff/60:.1f} min)...")
    if dry_run:
        log.info("[DRY RUN] Skipping wait.")
        return
    if diff > 5:
        time.sleep(diff - 5)
    while datetime.now(PT) < target:
        time.sleep(0.05)
    log.info("GO GO GO!")


def time_in_window(time_str, earliest=None, latest=None):
    if earliest is None:
        earliest = EARLIEST_TIME
    if latest is None:
        latest = LATEST_TIME
    try:
        if " " in time_str and "-" in time_str.split(" ")[0]:
            parsed = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        else:
            cleaned = time_str.strip().lower().replace(" ", "")
            for fmt in ["%I:%M%p", "%H:%M"]:
                try:
                    parsed = datetime.strptime(cleaned, fmt)
                    break
                except ValueError:
                    continue
            else:
                return False
        earliest_dt = datetime.strptime(earliest, "%H:%M")
        latest_dt   = datetime.strptime(latest,   "%H:%M")
        return earliest_dt.time() <= parsed.time() <= latest_dt.time()
    except Exception:
        return False


def _parse_course_code(course_code):
    parts = course_code.split("-", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else (parts[0], parts[0])


def _ss(page, name, log_dir=None):
    path = os.path.join(log_dir, name) if log_dir else name
    try:
        page.screenshot(path=path)
    except Exception:
        pass


def run_bot(headless=False, dry_run=False, no_wait=False, override_date=None,
            config=None, log_dir=None):

    if config:
        username        = config.get("username", USERNAME)
        password        = config.get("password", PASSWORD)
        course_name     = config.get("course_name", COURSE_NAME)
        course_code     = config.get("course_code", COURSE_CODE)
        num_players     = int(config.get("num_players", NUM_PLAYERS))
        num_holes       = int(config.get("num_holes", NUM_HOLES))
        target_day      = config.get("target_day", TARGET_DAY)
        earliest_time   = config.get("earliest_time", EARLIEST_TIME)
        latest_time     = config.get("latest_time", LATEST_TIME)
        preferred_time  = config.get("preferred_time")
        allow_fallback  = config.get("allow_fallback", True)
        dry_run         = config.get("dry_run", dry_run)
        captcha_key     = config.get("twocaptcha_key", TWOCAPTCHA_KEY)
    else:
        username        = USERNAME
        password        = PASSWORD
        course_name     = COURSE_NAME
        course_code     = COURSE_CODE
        num_players     = NUM_PLAYERS
        num_holes       = NUM_HOLES
        target_day      = TARGET_DAY
        earliest_time   = EARLIEST_TIME
        latest_time     = LATEST_TIME
        preferred_time  = os.getenv("PREFERRED_TIME")
        allow_fallback  = True
        captcha_key     = TWOCAPTCHA_KEY

    course_codes = [c.strip() for c in course_code.split(",")]
    course_names = [n.strip() for n in course_name.split(",")]
    while len(course_names) < len(course_codes):
        course_names.append("Unknown")

    if not username or not password:
        log.error("Missing credentials! Set FOREUP_EMAIL and FOREUP_PASSWORD in .env")
        sys.exit(1)

    if override_date:
        date_obj = datetime.strptime(override_date, "%m/%d/%Y").date()
    else:
        date_obj = get_target_date(target_day)

    date_disp = format_date_display(date_obj)
    facility_id, schedule_id = _parse_course_code(course_codes[0])
    booking_url = (
        f"https://foreupsoftware.com/index.php/booking"
        f"/{facility_id}/{schedule_id}#/teetimes"
    )

    log.info("=" * 60)
    log.info("Tee Time Sniper — San Diego Municipal Golf (ForeUp)")
    log.info("=" * 60)
    log.info(f"Course(s):      {', '.join(course_names)}")
    log.info(f"Target date:    {date_disp}")
    log.info(f"Time window:    {earliest_time} – {latest_time}")
    if preferred_time:
        log.info(f"Preferred time: {preferred_time}")
    log.info(f"Players:        {num_players}  |  Holes: {num_holes}")
    log.info(f"Dry run:        {dry_run}")
    log.info("=" * 60)

    if not no_wait:
        log.info("Waiting for 7 PM PT tee time drop...")
        wait_for_drop(dry_run=dry_run)
    else:
        log.info("Skipped wait (--no-wait).")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=50)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.set_default_timeout(30000)

        def ss(name):
            _ss(page, name, log_dir)

        try:
            # ── Step 1: Login ─────────────────────────────────────────────
            log.info("Step 1: Logging in...")
            page.goto(
                f"https://foreupsoftware.com/index.php/booking/{facility_id}#/login",
                wait_until="networkidle",
            )
            time.sleep(1)
            ss("debug_login_page.png")

            for sel in ["input[name='username']", "input[placeholder='Username']",
                        "input[name='email']", "input[type='email']", "input[type='text']"]:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    page.fill(sel, username)
                    break

            for sel in ["input[name='password']", "input[type='password']"]:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    page.fill(sel, password)
                    break

            for sel in ['button:has-text("SIGN IN")', 'button:has-text("Sign In")',
                        'button[type="submit"]', 'input[type="submit"]']:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    break

            page.wait_for_load_state("networkidle")
            time.sleep(1)
            ss("debug_login_result.png")
            log.info("  Logged in.")

            # ── Step 2: Navigate to booking page ──────────────────────────
            log.info("Step 2: Navigating to tee times...")
            page.goto(booking_url, wait_until="domcontentloaded")
            time.sleep(3)
            ss("debug_after_nav.png")

            # ── Step 3: Click booking class button ────────────────────────
            # "Resident (0-7 days)" for Torrey Pines
            # "Standard Tee Times (0-7 days)" for Mission Bay
            body_text = page.inner_text("body").lower()
            if any(kw in body_text for kw in ["please read", "resident", "standard", "tee time"]):
                log.info("Step 3: Clicking booking class button...")
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1)

                clicked_class = False
                for phrase in ["Resident (0 - 7", "Resident (0-7", "Resident",
                               "Standard Tee Times (0-7", "Standard Tee Times",
                               "Standard", "Public", "General Public"]:
                    # Use JS text search to avoid CSS selector issues with parens
                    el_handle = page.evaluate_handle("""(phrase) => {
                        const els = Array.from(document.querySelectorAll('a, button'));
                        return els.find(e =>
                            e.textContent.includes(phrase) && e.offsetParent !== null
                        ) || null;
                    }""", phrase)
                    try:
                        el = el_handle.as_element()
                    except Exception:
                        el = None
                    if el and el.is_visible():
                        log.info(f"  Clicking: {el.inner_text()[:60]}")
                        el.click()
                        page.wait_for_load_state("networkidle")
                        time.sleep(2)
                        ss("debug_after_booking_class.png")
                        clicked_class = True
                        break

                if not clicked_class:
                    all_btns = page.evaluate(
                        "() => Array.from(document.querySelectorAll('a, button'))"
                        ".filter(e => e.offsetParent !== null)"
                        ".map(e => e.textContent.trim()).filter(t => t.length > 2 && t.length < 60)"
                        ".join(' | ')"
                    )
                    log.warning(f"  No booking class button found. Visible: {all_btns[:400]}")

            # ── Step 4: Jump to target date via calendar ──────────────────
            log.info(f"Step 4: Jumping to {date_disp} via calendar...")
            target_day_num = date_obj.day
            target_month   = date_obj.strftime("%B %Y")
            time.sleep(1)

            # Use simple one-liner JS calls to avoid multiline parse issues
            for _ in range(3):
                cal_header = page.evaluate(
                    "() => { var h = document.querySelector('.datepicker-switch') || "
                    "document.querySelector('.calendar .month'); "
                    "return h ? h.textContent.trim() : ''; }"
                )
                log.info(f"  Calendar header: {cal_header}")
                if target_month.split()[0][:3].lower() in (cal_header or "").lower():
                    break
                page.evaluate(
                    "() => { var n = document.querySelector('.glyphicon-chevron-right'); "
                    "if (n && n.parentElement) n.parentElement.click(); }"
                )
                time.sleep(0.5)

            clicked_date = page.evaluate(
                "(d) => { var cells = Array.from(document.querySelectorAll('td')); "
                "var day = cells.find(function(c) { "
                "return c.textContent.trim() === String(d) "
                "&& !c.classList.contains('disabled') "
                "&& !c.classList.contains('old') "
                "&& !c.classList.contains('new') "
                "&& c.offsetParent !== null; }); "
                "if (day) { day.click(); return day.textContent.trim(); } return null; }",
                target_day_num
            )

            if clicked_date:
                log.info(f"  Clicked day: {clicked_date}")
                time.sleep(2)
            else:
                log.warning("  Calendar click failed — may already be on correct date")

            ss("debug_teetimes_page.png")

            # ── Step 5: Find best tee time card ───────────────────────────
            log.info(f"Step 5: Finding best tee time in {earliest_time}–{latest_time}...")
            try:
                page.wait_for_selector(".time", timeout=8000)
            except Exception:
                pass

            all_cards = page.query_selector_all(".time")
            log.info(f"  {len(all_cards)} cards found.")

            target_card   = None
            fallback_card = None
            selected_text = None

            for card in all_cards:
                text      = card.inner_text().strip()
                time_part = text.split("\n")[0].strip()
                hhmm      = None
                for fmt in ["%I:%M%p", "%I:%M %p"]:
                    try:
                        hhmm = datetime.strptime(time_part, fmt).strftime("%H:%M")
                        break
                    except Exception:
                        continue
                if not hhmm:
                    continue

                if time_in_window(f"{date_obj} {hhmm}", earliest_time, latest_time):
                    if preferred_time and hhmm == preferred_time:
                        target_card   = card
                        selected_text = time_part
                        log.info(f"  Preferred match: {time_part}")
                        break
                    if target_card is None:
                        target_card   = card
                        selected_text = time_part
                elif fallback_card is None and allow_fallback:
                    fallback_card = card

            if not target_card:
                if fallback_card and allow_fallback:
                    log.warning("  No card in window — using fallback")
                    target_card   = fallback_card
                    selected_text = fallback_card.inner_text().strip().split("\n")[0]
                elif all_cards:
                    log.warning("  No card in window — using first card")
                    target_card   = all_cards[0]
                    selected_text = all_cards[0].inner_text().strip().split("\n")[0]
                else:
                    log.error("  No tee time cards found.")
                    ss("debug_no_cards.png")
                    browser.close()
                    return (False, None)

            log.info(f"  Selected: {selected_text}")

            if dry_run:
                log.info("[DRY RUN] Would click this card — not booking.")
                ss("dry_run_result.png")
                browser.close()
                return (True, None)

            # ── Step 6: Open booking modal ────────────────────────────────
            target_card.click()
            time.sleep(2)
            ss("debug_booking_modal.png")
            log.info("Step 6: Modal open.")

            # ── Step 7: Select players (decoy + target) ───────────────────
            log.info(f"Step 7: Selecting {num_players} player(s)...")
            time.sleep(1)
            decoy = 2 if num_players != 2 else 3

            def click_player_btn(n):
                try:
                    modal = page.locator(".modal-dialog, .modal-content, .modal")
                    btn   = modal.locator("a").filter(has_text=str(n)).first
                    if btn.count() > 0 and btn.is_visible():
                        btn.click()
                        return f"modal-a:{n}"
                except Exception:
                    pass
                try:
                    result = page.evaluate(f"""() => {{
                        const btn = Array.from(document.querySelectorAll('a'))
                            .find(b => b.textContent.trim() === '{n}' && b.offsetParent !== null);
                        if (btn) {{ btn.click(); return btn.className; }}
                        return null;
                    }}""")
                    return f"js:{result}"
                except Exception as e:
                    return f"failed:{e}"

            log.info(f"  Decoy ({decoy}): {click_player_btn(decoy)}")
            time.sleep(0.4)
            log.info(f"  Target ({num_players}): {click_player_btn(num_players)}")
            time.sleep(0.5)

            if not page.query_selector(':text("Please select the number")'):
                log.info("  Player count confirmed.")
            else:
                log.warning("  Player error still showing — proceeding anyway")

            # ── Step 8: Click Book Time ────────────────────────────────────
            log.info("Step 8: Clicking Book Time...")
            for sel in ['button:has-text("Book Time")', 'button:has-text("Book")']:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    log.info("  Clicked.")
                    break
            time.sleep(3)
            ss("debug_after_book_click.png")

            # ── Step 9: Solve reCAPTCHA via 2captcha ──────────────────────
            if captcha_key:
                sitekey = page.evaluate("""() => {
                    const el = document.querySelector('[data-sitekey]');
                    return el ? el.getAttribute('data-sitekey') : null;
                }""")
                log.info(f"  reCAPTCHA sitekey: {sitekey}")

                if sitekey:
                    log.info("Step 9: Solving reCAPTCHA via 2captcha...")
                    try:
                        r   = requests.post("https://2captcha.com/in.php", data={
                            "key": captcha_key, "method": "userrecaptcha",
                            "googlekey": sitekey, "pageurl": page.url, "json": 1,
                        })
                        res = r.json()
                        if res.get("status") == 1:
                            captcha_id = res["request"]
                            log.info(f"  Job {captcha_id} submitted — polling...")
                            token = None
                            for _ in range(24):  # up to 2 minutes
                                time.sleep(5)
                                pr = requests.get("https://2captcha.com/res.php", params={
                                    "key": captcha_key, "action": "get",
                                    "id": captcha_id, "json": 1,
                                }).json()
                                if pr.get("status") == 1:
                                    token = pr["request"]
                                    log.info(f"  Solved! {token[:40]}...")
                                    break
                                elif pr.get("request") != "CAPCHA_NOT_READY":
                                    log.error(f"  2captcha error: {pr}")
                                    break

                            if token:
                                page.evaluate("""(t) => {
                                    const r = document.getElementById('g-recaptcha-response');
                                    if (r) r.value = t;
                                    document.querySelectorAll('[name="g-recaptcha-response"]')
                                        .forEach(e => e.value = t);
                                    try {
                                        const id = Object.keys(
                                            window.___grecaptcha_cfg?.clients || {})[0];
                                        if (id !== undefined) {
                                            const c = window.___grecaptcha_cfg.clients[id];
                                            for (const k of Object.keys(c)) {
                                                if (c[k]?.callback) { c[k].callback(t); break; }
                                            }
                                        }
                                    } catch(e) {}
                                }""", token)
                                log.info("  Token injected.")
                                time.sleep(1)
                                for sel in ['button:has-text("Book Time")', 'button:has-text("Book")']:
                                    btn = page.query_selector(sel)
                                    if btn and btn.is_visible():
                                        btn.click()
                                        log.info("  Re-clicked Book Time after captcha.")
                                        break
                        else:
                            log.error(f"  2captcha submit failed: {res}")
                    except Exception as ce:
                        log.error(f"  2captcha error: {ce}")
                else:
                    log.info("  No reCAPTCHA present — proceeding.")
            else:
                log.warning("  No TWOCAPTCHA_KEY — cannot auto-solve reCAPTCHA.")
                log.warning("  Add TWOCAPTCHA_KEY to .env (sign up at 2captcha.com, ~$3/1000 solves)")

            # ── Step 10: Check result ──────────────────────────────────────
            time.sleep(5)
            ss("booking_result.png")
            page_text = page.inner_text("body").lower()
            log.info(f"  Page text: {page_text[:400]}")

            if "please select the number of players" in page_text or "trouble booking" in page_text:
                log.error("  Booking failed — check booking_result.png")
                browser.close()
                return (False, None)

            if any(w in page_text for w in [
                "your reservation", "booking confirmed", "you're booked",
                "tee time confirmed", "reservation id", "confirmation",
                "successfully booked", "booked successfully", "thank you",
            ]):
                log.info("=" * 60)
                log.info("TEE TIME BOOKED SUCCESSFULLY!")
                log.info(f"   Course:  {course_names[0]}")
                log.info(f"   Date:    {date_disp}")
                log.info(f"   Time:    {selected_text}")
                log.info(f"   Players: {num_players}  |  Holes: {num_holes}")
                log.info("=" * 60)
                try:
                    os.system(
                        f'osascript -e \'display notification '
                        f'"Booked {selected_text} at {course_names[0]} on {date_disp}" '
                        f'with title "Tee Time Booked!"\''
                    )
                except Exception:
                    pass
                browser.close()
                return (True, None)

            log.warning("  Booking result ambiguous — check booking_result.png")
            browser.close()
            return (False, None)

        except Exception as e:
            log.error(f"Browser error: {e}")
            try:
                ss("debug_browser_error.png")
            except Exception:
                pass
            browser.close()
            return (False, None)


# ─── Dashboard integration ────────────────────────────────────────────────────

def cancel_booking(page, target_description_fragment, log_dir=None):
    log.warning(f"Auto-cancellation not implemented. Cancel manually: {target_description_fragment}")
    return False


def run_bot_with_logging(config, log_dir):
    """Run the bot and capture log output. Returns (success, fallback_desc, log_text)."""
    import io
    os.makedirs(log_dir, exist_ok=True)
    buf     = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger = logging.getLogger("tee-sniper")
    logger.addHandler(handler)
    fallback_desc = None
    try:
        success, fallback_desc = run_bot(
            headless=True,
            dry_run=config.get("dry_run", False),
            no_wait=config.get("no_wait", False),  # False = use internal 7PM countdown
            config=config,
            log_dir=log_dir,
        )
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        success = False
    finally:
        logger.removeHandler(handler)
    return success, fallback_desc, buf.getvalue()


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="⛳ San Diego Municipal Golf — Tee Time Sniper (ForeUp)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python book_tee_time.py --no-wait --dry-run   # Test full flow, no booking
  python book_tee_time.py --no-wait             # Book immediately (skip 7 PM wait)
  python book_tee_time.py                        # Full run — waits for 7 PM PT drop
  python book_tee_time.py --headless             # Run without visible browser
        """,
    )
    parser.add_argument("--dry-run",  action="store_true", help="Test mode — don't actually book")
    parser.add_argument("--no-wait",  action="store_true", help="Skip waiting for 7 PM PT drop")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--debug",    action="store_true", help="Enable debug logging")
    parser.add_argument("--date",     type=str, default=None, help="Override target date (MM/DD/YYYY)")
    args = parser.parse_args()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    success, _ = run_bot(
        headless=args.headless,
        dry_run=args.dry_run,
        no_wait=args.no_wait,
        override_date=args.date,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
