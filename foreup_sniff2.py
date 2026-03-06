#!/usr/bin/env python3
"""
ForeUp tee-times endpoint sniffer.
Logs in via API directly (no browser UI), then loads the booking page
in a browser with the auth cookies set so the tee-times call fires.

Run:  python3 foreup_sniff2.py
Then check foreup_api_calls2.json
"""

import json, os, time, requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

EMAIL    = os.getenv("FOREUP_EMAIL", "")
PASSWORD = os.getenv("FOREUP_PASSWORD", "")

FACILITY_ID = "19347"
SCHEDULE_ID = "1468"   # Torrey Pines North
DATE        = "03/07/2026"

# ── Step 1: Login via requests to get JWT + cookies ──────────────────────────
print("[1] Logging in via API...")
sess = requests.Session()
sess.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "api-key": "no_limits",
    "x-fu-golfer-location": "foreup",
    "Referer": f"https://foreupsoftware.com/index.php/booking/{FACILITY_ID}/{SCHEDULE_ID}",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
})

login_resp = sess.post(
    "https://foreupsoftware.com/index.php/api/booking/users/login",
    data={
        "username": EMAIL,
        "password": PASSWORD,
        "course_id": FACILITY_ID,
        "api_key": "no_limits",
        "booking_class_id": "",
    },
    timeout=15,
)
login_data = login_resp.json()
jwt = login_data.get("jwt", "")
person_id = login_data.get("person_id", "")
print(f"   JWT: {jwt[:40]}...")
print(f"   person_id: {person_id}")
print(f"   logged_in: {login_data.get('logged_in')}")

# Collect cookies from the requests session to inject into Playwright
api_cookies = [
    {"name": c.name, "value": c.value, "domain": "foreupsoftware.com", "path": "/"}
    for c in sess.cookies
]
print(f"   Cookies from login: {[c['name'] for c in api_cookies]}")

# ── Step 2: Now probe the tee-times endpoints directly via requests ───────────
print("\n[2] Probing tee-times endpoints with authenticated session...")
sess.headers["x-authorization"] = f"Bearer {jwt}"

base = "https://foreupsoftware.com"
params_base = {
    "date": DATE,
    "time": "all",
    "holes": "18",
    "players": "2",
    "booking_class": "0",
    "schedule_id": SCHEDULE_ID,
    "api_key": "no_limits",
}

candidates = [
    (f"{base}/index.php/api/booking/tee-times",               {**params_base}),
    (f"{base}/index.php/api/booking/tee-times",               {**params_base, "facility_id": FACILITY_ID}),
    (f"{base}/index.php/api/booking/tee-times/{FACILITY_ID}", {**params_base}),
    (f"{base}/index.php/api/booking/tee-times/{FACILITY_ID}/{SCHEDULE_ID}", {**params_base}),
    (f"{base}/index.php/api/booking/times",                   {**params_base, "facility_id": FACILITY_ID}),
    (f"{base}/index.php/api/tee_times",                       {**params_base, "facility_id": FACILITY_ID}),
    (f"{base}/api_rest/index.php/courses/{FACILITY_ID}/teetimes", {"date": DATE, "holes": "18", "players": "2", "schedule_id": SCHEDULE_ID}),
]

results = {}
for url, params in candidates:
    try:
        r = sess.get(url, params=params, timeout=10)
        results[url] = {"status": r.status_code, "body": r.text[:500]}
        marker = "✓" if r.status_code == 200 else "✗"
        print(f"  {marker} {r.status_code}  {url}")
        if r.status_code == 200:
            print(f"       BODY: {r.text[:300]}")
    except Exception as e:
        results[url] = {"error": str(e)}
        print(f"  ERR  {url}: {e}")

# ── Step 3: Open browser, inject auth, load tee times page, capture calls ────
print("\n[3] Opening browser to capture tee-times network call...")
captured = []

def handle_request(request):
    url = request.url
    if "foreupsoftware.com" in url:
        entry = {"type": "REQUEST", "method": request.method, "url": url}
        if request.method in ("POST", "PUT"):
            try: entry["post_data"] = request.post_data
            except: pass
        captured.append(entry)
        print(f"  → {request.method} {url}")

def handle_response(response):
    url = response.url
    if "foreupsoftware.com" in url:
        entry = {"type": "RESPONSE", "status": response.status, "url": url}
        try:
            body = response.text()
            if body.strip().startswith(("{", "[")):
                try:    entry["body"] = json.loads(body)
                except: entry["body_raw"] = body[:2000]
        except: pass
        captured.append(entry)
        print(f"  ← {response.status} {url}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=100)
    context = browser.new_context(viewport={"width": 1280, "height": 900})

    # Inject auth cookie + JWT header via route interception
    booking_url = f"https://foreupsoftware.com/index.php/booking/{FACILITY_ID}/{SCHEDULE_ID}#/teetimes"

    # Add cookies from the requests session
    if api_cookies:
        context.add_cookies(api_cookies)

    # Intercept all requests to inject the JWT header
    def inject_auth(route):
        headers = {**route.request.headers, "x-authorization": f"Bearer {jwt}", "api-key": "no_limits"}
        route.continue_(headers=headers)

    context.route("**/*", inject_auth)

    page = context.new_page()
    page.on("request", handle_request)
    page.on("response", handle_response)

    print(f"  Loading: {booking_url}")
    page.goto(booking_url, wait_until="networkidle")
    time.sleep(8)  # Wait for tee times to auto-load via JS

    page.screenshot(path="foreup_teetimes_loaded.png")
    print("  Screenshot: foreup_teetimes_loaded.png")

    browser.close()

# ── Save results ──────────────────────────────────────────────────────────────
output = {
    "direct_api_probe": results,
    "browser_captured": captured,
}
with open("foreup_api_calls2.json", "w") as f:
    json.dump(output, f, indent=2, default=str)

print(f"\n✓ Saved foreup_api_calls2.json")
print("  Look for 200 responses in direct_api_probe, and tee-times calls in browser_captured")
