#!/usr/bin/env python3
"""Tee Time Sniper — Web Dashboard

Run with: python run_dashboard.py
Open: http://127.0.0.1:5050
"""

from dashboard import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=True)
