import requests
import json
from datetime import datetime, timedelta

API_KEY = "YOUR_API_KEY_HERE"
BASE_URL = "https://api.api-ninjas.com/v1/earningscalendar"

# Load watchlist
with open("watchlist.json", "r") as f:
    tickers = json.load(f)["tickers"]

# Date range (next 30 days)
today = datetime.utcnow().date()
end_date = today + timedelta(days=30)

events = []

for ticker in tickers:
    response = requests.get(
        BASE_URL,
        headers={"X-Api-Key": API_KEY},
        params={
            "ticker": ticker,
            "start_date": today.isoformat(),
            "end_date": end_date.isoformat()
        }
    )

    if response.status_code != 200:
        print(f"Error fetching {ticker}")
        continue

    data = response.json()

    for item in data:
        date_str = item.get("date")
        if not date_str:
            continue

        dt = datetime.strptime(date_str, "%Y-%m-%d")

        # Default time (earnings often pre/post market, but API may not specify exact time)
        start = dt.strftime("%Y%m%dT130000Z")  # 6am PT placeholder
        end = dt.strftime("%Y%m%dT140000Z")

        summary = f"{ticker} Earnings"
        description = f"Earnings report for {ticker}"

        event = f"""BEGIN:VEVENT
UID:{ticker}-{date_str}
DTSTAMP:{datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}
DTSTART:{start}
DTEND:{end}
SUMMARY:{summary}
DESCRIPTION:{description}
END:VEVENT
"""
        events.append(event)

# Build ICS file
ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Custom Earnings Calendar//EN
{"".join(events)}
END:VCALENDAR
"""

with open("earnings.ics", "w") as f:
    f.write(ics_content)

print("earnings.ics generated!")