#!/usr/bin/env python3
"""
ForeUp network sniffer — intercepts actual API calls made by the browser
so we can identify the correct login endpoint, tee-times endpoint, and
request/response shape.

Run:  python3 foreup_sniff.py
Then check foreup_api_calls.json for the captured requests.
"""

import json
import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

EMAIL    = os.getenv("FOREUP_EMAIL", "")
PASSWORD = os.getenv("FOREUP_PASSWORD", "")

# Torrey Pines South booking page
BOOKING_URL = "https://foreupsoftware.com/index.php/booking/19347/1469#/teetimes"

captured = []

def handle_request(request):
    url = request.url
    if "foreupsoftware.com" in url and any(k in url for k in [
        "api", "login", "tee", "booking", "ajax", "auth", "token", "user", "session"
    ]):
        entry = {
            "type": "REQUEST",
            "method": request.method,
            "url": url,
            "headers": dict(request.headers),
        }
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                entry["post_data"] = request.post_data
            except Exception:
                pass
        captured.append(entry)
        print(f"  → {request.method} {url}")

def handle_response(response):
    url = response.url
    if "foreupsoftware.com" in url and any(k in url for k in [
        "api", "login", "tee", "booking", "ajax", "auth", "token", "user", "session"
    ]):
        entry = {
            "type": "RESPONSE",
            "status": response.status,
            "url": url,
        }
        try:
            body = response.text()
            # Only capture JSON responses (skip HTML/images)
            if body.strip().startswith(("{", "[")):
                try:
                    entry["body"] = json.loads(body)
                except Exception:
                    entry["body_raw"] = body[:2000]
        except Exception:
            pass
        captured.append(entry)
        print(f"  ← {response.status} {url}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=200)
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()

    page.on("request", handle_request)
    page.on("response", handle_response)

    # Step 1: Load booking page (triggers session setup)
    print("\n[1] Loading booking page...")
    page.goto(BOOKING_URL, wait_until="networkidle")

    # Step 2: Look for and click the login button/link
    print("\n[2] Looking for login UI...")
    import time
    time.sleep(2)

    # Try common login selectors on ForeUp
    login_selectors = [
        'button:has-text("Sign In")',
        'button:has-text("Log In")',
        'button:has-text("Login")',
        'a:has-text("Sign In")',
        'a:has-text("Log In")',
        'a:has-text("Login")',
        '[data-action="login"]',
        '.login-btn',
        '#login-btn',
    ]
    clicked = False
    for sel in login_selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                print(f"  Found login button: {sel}")
                el.click()
                time.sleep(2)
                clicked = True
                break
        except Exception:
            continue

    if not clicked:
        print("  Could not find login button automatically.")
        print("  Please click the login button manually in the browser window.")
        input("  Press Enter once the login form is visible...")

    # Step 3: Fill in credentials
    print("\n[3] Filling credentials...")
    time.sleep(1)

    email_selectors = [
        'input[type="email"]',
        'input[name="email"]',
        'input[placeholder*="email" i]',
        'input[id*="email" i]',
        '#email',
    ]
    pw_selectors = [
        'input[type="password"]',
        'input[name="password"]',
        'input[id*="password" i]',
        '#password',
    ]

    filled_email = False
    for sel in email_selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.fill(EMAIL)
                print(f"  Filled email via: {sel}")
                filled_email = True
                break
        except Exception:
            continue

    filled_pw = False
    for sel in pw_selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.fill(PASSWORD)
                print(f"  Filled password via: {sel}")
                filled_pw = True
                break
        except Exception:
            continue

    if not filled_email or not filled_pw:
        print("  Could not auto-fill form. Please fill in credentials manually.")
        input("  Press Enter once you've filled in the form (before submitting)...")

    # Step 4: Submit login form
    print("\n[4] Submitting login form...")
    submit_selectors = [
        'button[type="submit"]',
        'button:has-text("Sign In")',
        'button:has-text("Log In")',
        'button:has-text("Login")',
        'input[type="submit"]',
    ]
    submitted = False
    for sel in submit_selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                print(f"  Submitted via: {sel}")
                submitted = True
                break
        except Exception:
            continue

    if not submitted:
        print("  Could not auto-submit. Please click the login/submit button manually.")
        input("  Press Enter once you've submitted the login form...")

    page.wait_for_load_state("networkidle")
    time.sleep(3)
    print("  Login step complete.")

    # Step 5: Wait for tee times to load
    print("\n[5] Waiting for tee times page to load...")
    time.sleep(3)
    page.screenshot(path="foreup_after_login.png")
    print("  Screenshot saved: foreup_after_login.png")

    browser.close()

# Save all captured API calls
out_path = "foreup_api_calls.json"
with open(out_path, "w") as f:
    json.dump(captured, f, indent=2, default=str)

print(f"\n✓ Captured {len(captured)} API calls → {out_path}")
print("\nKey calls to look for:")
print("  - Login POST request (method=POST, url contains 'login' or 'auth')")
print("  - Tee times GET request (url contains 'tee' or 'times' or 'booking')")
print("  - Any POST with email/password in post_data")
