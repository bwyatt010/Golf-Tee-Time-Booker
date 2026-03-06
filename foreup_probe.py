#!/usr/bin/env python3
"""
Probe /index.php/api/booking/times with every param variation
to find what returns actual tee time data.
"""

import json, os, requests
from dotenv import load_dotenv

load_dotenv()

EMAIL    = os.getenv("FOREUP_EMAIL", "")
PASSWORD = os.getenv("FOREUP_PASSWORD", "")

FACILITY_ID = "19347"
SCHEDULE_ID = "1468"   # Torrey Pines North
DATE        = "03/07/2026"

# Login first
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
    data={"username": EMAIL, "password": PASSWORD, "course_id": FACILITY_ID, "api_key": "no_limits", "booking_class_id": ""},
    timeout=15,
)
login_data = login_resp.json()
jwt = login_data.get("jwt", "")
sess.headers["x-authorization"] = f"Bearer {jwt}"
sess.headers.pop("Content-Type")
print(f"Logged in. JWT: {jwt[:30]}...\n")

BASE = "https://foreupsoftware.com/index.php/api/booking/times"

variants = [
    # vary schedule_id param name
    {"date": DATE, "time": "all", "holes": "18", "players": "2", "schedule_id": SCHEDULE_ID, "api_key": "no_limits"},
    {"date": DATE, "time": "all", "holes": "18", "players": "2", "schedule_id": SCHEDULE_ID, "facility_id": FACILITY_ID, "api_key": "no_limits"},
    {"date": DATE, "time": "all", "holes": "18", "players": "2", "schedule_ids[]": SCHEDULE_ID, "api_key": "no_limits"},
    {"date": DATE, "time": "all", "holes": "18", "players": "2", "course_id": SCHEDULE_ID, "api_key": "no_limits"},
    {"date": DATE, "time": "all", "holes": "18", "players": "2", "course_id": FACILITY_ID, "schedule_id": SCHEDULE_ID, "api_key": "no_limits"},
    # without time=all
    {"date": DATE, "holes": "18", "players": "2", "schedule_id": SCHEDULE_ID, "api_key": "no_limits"},
    # with booking_class
    {"date": DATE, "time": "all", "holes": "18", "players": "2", "schedule_id": SCHEDULE_ID, "booking_class": "0", "api_key": "no_limits"},
    {"date": DATE, "time": "all", "holes": "18", "players": "2", "schedule_id": SCHEDULE_ID, "booking_class_id": "0", "api_key": "no_limits"},
    # different date formats
    {"date": "2026-03-07", "time": "all", "holes": "18", "players": "2", "schedule_id": SCHEDULE_ID, "api_key": "no_limits"},
    # Torrey South (1469) — in case 1468 has no times yet
    {"date": DATE, "time": "all", "holes": "18", "players": "2", "schedule_id": "1469", "api_key": "no_limits"},
    # Balboa (19348) — single-course facility
    {"date": DATE, "time": "all", "holes": "18", "players": "2", "schedule_id": "19348", "api_key": "no_limits"},
    # Mission Bay (19346)
    {"date": DATE, "time": "all", "holes": "18", "players": "2", "schedule_id": "19346", "api_key": "no_limits"},
]

results = []
for params in variants:
    r = sess.get(BASE, params=params, timeout=10)
    body = r.text[:300]
    marker = "✓" if (r.status_code == 200 and body != "[]") else ("~" if r.status_code == 200 else "✗")
    key_param = {k: v for k, v in params.items() if k not in ("api_key", "time", "holes", "players")}
    print(f"  {marker} {r.status_code}  params={key_param}")
    if body not in ("[]", ""):
        print(f"       {body}")
    results.append({"params": params, "status": r.status_code, "body": r.text[:1000]})

with open("foreup_times_probe.json", "w") as f:
    json.dump(results, f, indent=2)
print("\n✓ Saved foreup_times_probe.json")
