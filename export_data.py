#!/usr/bin/env python3
"""Export backtest data to CSV files"""

import sqlite3
import csv
from pathlib import Path

DB_PATH = "data/backtest_results.db"
OUTPUT_DIR = "data/exports"

def export_table(conn, table_name, output_file):
    """Export a table to CSV"""
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name}")

    rows = cursor.fetchall()
    if not rows:
        print(f"  {table_name}: No data")
        return

    columns = [desc[0] for desc in cursor.description]

    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)

    print(f"  {table_name}: {len(rows)} rows → {output_file}")

def main():
    # Create output directory
    Path(OUTPUT_DIR).mkdir(exist_ok=True)

    # Connect to database
    conn = sqlite3.connect(DB_PATH)

    print("Exporting data...\n")

    # Export each table
    export_table(conn, "backtest_sessions", f"{OUTPUT_DIR}/sessions.csv")
    export_table(conn, "ai_decisions", f"{OUTPUT_DIR}/decisions.csv")
    export_table(conn, "trades", f"{OUTPUT_DIR}/trades.csv")
    export_table(conn, "portfolio_snapshots", f"{OUTPUT_DIR}/snapshots.csv")

    conn.close()
    print(f"\nDone! Files saved to {OUTPUT_DIR}/")

if __name__ == "__main__":
    main()
