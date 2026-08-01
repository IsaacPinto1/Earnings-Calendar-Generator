import requests
import json
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

API_KEY = os.getenv("API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
USE_CACHE = os.getenv("DEBUG", "False").lower() == "true"

BASE_URL = "https://api.earningsapi.com/v1/calendar/earnings"
CACHE_DIR = "cache"
STORAGE_BUCKET = "calendar"
STORAGE_PATH = "earnings.ics"

DAYS_AHEAD = 14        # how far forward to pull fresh data from the API
DAYS_OF_HISTORY = 365  # how far back to keep events in the published .ics

os.makedirs(CACHE_DIR, exist_ok=True)

if not API_KEY:
    print("Please set your API_KEY in .env")
    exit(1)

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("Please set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Load watchlist
with open("watchlist.json", "r") as f:
    tickers = set(json.load(f)["tickers"])

today = datetime.utcnow().date()


def get_time(report_time, date_str):
    # Map to approximate UTC times
    if report_time == "pre":
        return f"{date_str}T133000Z", f"{date_str}T143000Z"  # 6:30-7:30am PT
    elif report_time == "after":
        return f"{date_str}T210000Z", f"{date_str}T220000Z"  # 2-3pm PT
    else:
        return f"{date_str}T170000Z", f"{date_str}T180000Z"  # midday fallback


def fetch_forward_window():
    """Fetch the next DAYS_AHEAD days from the API and return rows to upsert."""
    rows = []
    seen = set()  # prevent duplicates within this run

    for i in range(DAYS_AHEAD):
        fetch_date = today + timedelta(days=i)
        date_str = fetch_date.isoformat()
        cache_file = f"{CACHE_DIR}/{date_str}.json"

        if USE_CACHE and os.path.exists(cache_file):
            with open(cache_file, "r") as f:
                data = json.load(f)
        else:
            response = requests.get(
                BASE_URL,
                params={"date": date_str, "apikey": API_KEY},
            )

            if response.status_code != 200:
                print(f"Error fetching {date_str}")
                continue

            data = response.json()

            with open(cache_file, "w") as f:
                json.dump(data, f, indent=2)

        for report_time in data:
            if report_time == "date":
                continue
            for item in data[report_time]:
                ticker = item.get("symbol")
                if ticker not in tickers:
                    continue

                uid = f"{ticker}-{date_str}"
                if uid in seen:
                    continue
                seen.add(uid)

                rows.append(
                    {
                        "uid": uid,
                        "ticker": ticker,
                        "report_date": date_str,
                        "report_time": report_time,
                        "eps_estimate": item.get("epsEstimate"),
                    }
                )

    return rows


def upsert_events(rows):
    """Write new/updated events to Supabase. Never deletes anything, so
    events that scroll out of the forward window stay in the table forever
    and become the historical record."""
    if not rows:
        print("No new events to upsert.")
        return

    supabase.table("earnings_events").upsert(rows, on_conflict="uid").execute()
    print(f"Upserted {len(rows)} events into Supabase.")


def load_calendar_window():
    """Pull everything from (today - DAYS_OF_HISTORY) to (today + DAYS_AHEAD)
    out of Supabase. This — not the API response — is what gets published,
    so past events are never dropped from the .ics file."""
    start_date = (today - timedelta(days=DAYS_OF_HISTORY)).isoformat()
    end_date = (today + timedelta(days=DAYS_AHEAD)).isoformat()

    response = (
        supabase.table("earnings_events")
        .select("*")
        .gte("report_date", start_date)
        .lte("report_date", end_date)
        .order("report_date")
        .execute()
    )
    return response.data


def build_ics(rows):
    events = []
    generated_at = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    for row in rows:
        ticker = row["ticker"]
        date_str = row["report_date"]
        report_time = row.get("report_time")
        eps_estimate = row.get("eps_estimate")

        start, end = get_time(report_time, date_str)
        label = report_time.upper() if report_time else "TBD"

        event = (
            "BEGIN:VEVENT\n"
            f"UID:{row['uid']}\n"
            f"DTSTAMP:{generated_at}\n"
            f"DTSTART:{start.replace('-', '').replace(':', '')}\n"
            f"DTEND:{end.replace('-', '').replace(':', '')}\n"
            f"SUMMARY:{ticker} Earnings ({label})\n"
            f"DESCRIPTION:{ticker} earnings report"
            f"\\nTime: {label}"
            f"\\nEPS Estimate: {eps_estimate if eps_estimate is not None else 'N/A'}\n"
            "END:VEVENT\n"
        )
        events.append(event)

    return (
        "BEGIN:VCALENDAR\n"
        "VERSION:2.0\n"
        "PRODID:-//Custom Earnings Calendar//EN\n"
        f"{''.join(events)}"
        "END:VCALENDAR\n"
    )


def publish_ics(ics_content):
    # Keep a local copy for debugging only — this file is no longer
    # committed to git, so this write is purely for local runs.
    with open("earnings.ics", "w") as f:
        f.write(ics_content)

    supabase.storage.from_(STORAGE_BUCKET).upload(
        STORAGE_PATH,
        ics_content.encode("utf-8"),
        {"content-type": "text/calendar", "upsert": "true"},
    )

    public_url = supabase.storage.from_(STORAGE_BUCKET).get_public_url(STORAGE_PATH)
    print(f"earnings.ics published: {public_url}")


if __name__ == "__main__":
    new_rows = fetch_forward_window()
    upsert_events(new_rows)

    all_rows = load_calendar_window()
    ics_content = build_ics(all_rows)
    publish_ics(ics_content)
