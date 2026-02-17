#!/usr/bin/env python3
"""
Fetch historical Fear & Greed Index data for backtest date ranges.

The Fear & Greed API (alternative.me) provides historical data.
This script fetches data for the date ranges used in your backtest.
"""

import sqlite3
import requests
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

def get_backtest_date_range(db_path: str):
    """Get the actual date range from the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("""
        SELECT MIN(timestamp) as earliest, MAX(timestamp) as latest
        FROM ai_decisions
    """)
    row = cursor.fetchone()
    conn.close()

    if row[0] and row[1]:
        earliest = datetime.fromisoformat(row[0])
        latest = datetime.fromisoformat(row[1])
        return earliest, latest
    return None, None

def fetch_feargreed_data(days_limit: int = 365):
    """
    Fetch Fear & Greed Index from alternative.me API.

    Note: The API provides historical data, but there may be limits on how far back.
    The free API provides up to ~2000 days of history.
    """
    url = f"https://api.alternative.me/fng/?limit={days_limit}&date_format=world"

    try:
        print(f"Fetching {days_limit} days of Fear & Greed data...")
        response = requests.get(url, timeout=30)

        if response.status_code == 200:
            data = response.json()
            if 'data' in data:
                print(f"Successfully fetched {len(data['data'])} data points")
                return data['data']
            else:
                print(f"Unexpected response format: {data}")
                return []
        else:
            print(f"API error: {response.status_code}")
            return []

    except Exception as e:
        print(f"Error fetching data: {e}")
        return []

def update_cache(cache_file: str, new_data: list):
    """Update the Fear & Greed cache file with new data."""
    # Load existing cache
    cache = {}
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            cache = json.load(f)
        print(f"Loaded existing cache with {len(cache)} entries")

    # Add new data
    added = 0
    for item in new_data:
        timestamp = item['timestamp']  # Format: "DD-MM-YYYY"
        value = int(item['value'])

        if timestamp not in cache:
            cache[timestamp] = value
            added += 1

    print(f"Added {added} new entries to cache")

    # Save cache
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    with open(cache_file, 'w') as f:
        json.dump(cache, f, indent=2)

    print(f"Cache saved with {len(cache)} total entries")
    return cache

def update_database_feargreed(db_path: str, cache: dict):
    """
    Update Fear & Greed values in the database using the cache.

    This re-matches timestamps from the database with the cached F&G data.
    """
    conn = sqlite3.connect(db_path)

    # Get all decisions with their timestamps
    cursor = conn.execute("SELECT id, timestamp FROM ai_decisions ORDER BY id")
    decisions = cursor.fetchall()

    print(f"\nUpdating {len(decisions)} decisions with Fear & Greed data...")

    updated = 0
    not_found = 0

    for dec_id, timestamp_str in decisions:
        # Parse timestamp and format to match cache key (DD-MM-YYYY)
        dt = datetime.fromisoformat(timestamp_str)
        cache_key = dt.strftime("%d-%m-%Y")

        if cache_key in cache:
            fg_value = cache[cache_key]

            # Update the database
            conn.execute(
                "UPDATE ai_decisions SET fear_greed_index = ? WHERE id = ?",
                (fg_value, dec_id)
            )
            updated += 1
        else:
            not_found += 1

    conn.commit()
    conn.close()

    print(f"  Updated: {updated}")
    print(f"  Not found in cache: {not_found}")

    if not_found > 0:
        print(f"\nWarning: {not_found} decisions have no matching Fear & Greed data.")
        print("This likely means the API doesn't have data for those dates.")
        print("These will keep their default value of 50.")

def main():
    db_path = "data/backtest_results.db"
    cache_file = "data/historical/fear_greed.json"

    print("Historical Fear & Greed Data Fetcher")
    print("="*60)

    # Check if database exists
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return

    # Get date range from database
    print("\nAnalyzing backtest date range...")
    earliest, latest = get_backtest_date_range(db_path)

    if not earliest or not latest:
        print("No data found in database")
        return

    print(f"Backtest date range: {earliest.date()} to {latest.date()}")

    # Calculate days needed
    days_needed = (datetime.now() - earliest).days + 30  # Add buffer

    # API limit is around 2000 days, but let's be conservative
    if days_needed > 2000:
        print(f"\nWarning: Need {days_needed} days of data, but API may only provide ~2000 days")
        days_needed = 2000

    print(f"Requesting {days_needed} days of Fear & Greed data...")

    # Fetch data
    new_data = fetch_feargreed_data(days_needed)

    if not new_data:
        print("\nFailed to fetch data. Exiting.")
        return

    # Check what date range we actually got
    dates = [datetime.strptime(item['timestamp'], "%d-%m-%Y") for item in new_data]
    api_earliest = min(dates)
    api_latest = max(dates)

    print(f"\nAPI provided data from: {api_earliest.date()} to {api_latest.date()}")

    if api_earliest > earliest:
        print(f"\nWarning: API data starts at {api_earliest.date()}, but backtest starts at {earliest.date()}")
        print(f"Missing {(api_earliest - earliest).days} days of data.")
        print("Decisions before API coverage will use default value (50).")

    # Update cache file
    print(f"\nUpdating cache file: {cache_file}")
    cache = update_cache(cache_file, new_data)

    # Update database
    print(f"\nUpdating database: {db_path}")
    update_database_feargreed(db_path, cache)

    print("\n" + "="*60)
    print("Done! You can now re-run the analysis script to see updated results.")

if __name__ == "__main__":
    main()
