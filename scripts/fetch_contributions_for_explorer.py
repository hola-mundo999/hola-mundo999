#!/usr/bin/env python3
"""Fetch contributions data for the 3D contribution explorer."""
import json
import os
import re
import requests
from bs4 import BeautifulSoup

USERNAME = os.environ.get("GH_PROFILE_USER", "hola-mundo999")
URL = f"https://github.com/users/{USERNAME}/contributions"

def fetch():
    resp = requests.get(URL, headers={"User-Agent": "profile-readme-bot/1.0"}, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    data = []
    for td in soup.select("td.ContributionCalendar-day"):
        date = td.get("data-date")
        if not date:
            continue
        td_id = td.get("id")
        tooltip_el = soup.find("tool-tip", attrs={"for": td_id}) if td_id else None
        text = tooltip_el.get_text(strip=True) if tooltip_el else ""
        m = re.match(r"(\d+)", text)
        count = int(m.group(1)) if m else 0
        level = int(td.get("data-level") or 0)
        data.append({"date": date, "count": count, "level": level})

    return data

if __name__ == "__main__":
    data = fetch()
    out_path = os.path.join(os.path.dirname(__file__), "..", "contribution-explorer", "data", "contributions.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote {len(data)} days to {out_path}")