import requests
import json
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY")
USE_CACHE = os.getenv("DEBUG", "False").lower() == "true"
BASE_URL = "https://api.earningsapi.com/v1/calendar/earnings"
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)



if not API_KEY:
    print("Please set your API_KEY in .env.local")
    exit(1)

# Load watchlist
with open("watchlist.json", "r") as f:
    tickers = set(json.load(f)["tickers"])

today = datetime.utcnow().date()
days_ahead = 14

events = []
seen = set()  # prevent duplicates

def get_time(report_time, date):
    # Map to approximate UTC times
    if report_time == "pre":
        return f"{date}T133000Z", f"{date}T143000Z"  # 6:30–7:30am PT
    elif report_time == "after":
        return f"{date}T210000Z", f"{date}T220000Z"  # 2–3pm PT
    else:
        return f"{date}T170000Z", f"{date}T180000Z"  # midday fallback

for i in range(days_ahead):
    date = today + timedelta(days=i)
    date_str = date.isoformat()

    cache_file = f"{CACHE_DIR}/{date_str}.json"

    if USE_CACHE and os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            data = json.load(f)
    else:
        response = requests.get(
            BASE_URL,
            params={
                "date": date_str,
                "apikey": API_KEY
            }
        )

        if response.status_code != 200:
            print(f"Error fetching {date_str}")
            continue

        data = response.json()

        with open(cache_file, "w") as f:
            json.dump(data, f, indent=2)

    date = data['date']
    for time in data:
        if time == "date":
            continue
        for item in data[time]:
            ticker = item.get("symbol")
            if ticker not in tickers:
                continue

            if (ticker, date_str) in seen:
                continue
            seen.add((ticker, date_str))

            report_time = time

            start, end = get_time(report_time, date_str)

            summary = f"{ticker} Earnings ({report_time.upper()})"
            description = f"{ticker} earnings report\nTime: {report_time.upper()}"

            eps_estimate = item.get("epsEstimate")

            event = (
                "BEGIN:VEVENT\n"
                f"UID:{ticker}-{date_str}\n"
                f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}\n"
                f"DTSTART:{start.replace('-', '').replace(':', '')}\n"
                f"DTEND:{end.replace('-', '').replace(':', '')}\n"
                f"SUMMARY:{ticker} Earnings{f' ({report_time.upper()})' if report_time else ''}\n"
                f"DESCRIPTION:{ticker} earnings report"+
                f"\\nTime: {report_time.upper() if report_time else 'TBD'}" +
                f"\\nEPS Estimate: {eps_estimate if eps_estimate is not None else 'N/A'}\n"
                "END:VEVENT\n"
            )
            events.append(event)

# Build ICS
ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Custom Earnings Calendar//EN
{"".join(events)}
END:VCALENDAR
"""

with open("earnings.ics", "w") as f:
    f.write(ics_content)

print("earnings.ics generated!")