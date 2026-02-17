#!/usr/bin/env python3
"""
Data Validation Tool
Scans historical data for errors (NaNs, zeros, gaps) without modifying original files.
"""

import os
import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = "data/historical"

def check_file(filepath):
    print(f"\nChecking {filepath}...")
    try:
        if filepath.suffix == '.parquet':
            df = pd.read_parquet(filepath)
        else:
            df = pd.read_csv(filepath)
    except Exception as e:
        print(f"  [ERROR] Could not read file: {e}")
        return

    issues = []
    
    # Check for required columns
    required = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"  [CRITICAL] Missing columns: {missing}")
        return

    # Check for NaNs
    if df.isnull().values.any():
        nan_cols = df.columns[df.isnull().any()].tolist()
        issues.append(f"Contains NaNs in columns: {nan_cols}")
        for col in nan_cols:
            count = df[col].isnull().sum()
            issues.append(f"  - {col}: {count} missing values")

    # Check for non-positive prices
    price_cols = ['open', 'high', 'low', 'close']
    for col in price_cols:
        if (df[col] <= 0).any():
            count = (df[col] <= 0).sum()
            issues.append(f"Found {count} non-positive values in '{col}'")

    # Check for time gaps (assuming 1H candles)
    if 'timestamp' in df.columns:
        try:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            diffs = df['timestamp'].diff()
            
            # Assuming 1 hour data (3600 seconds)
            # We allow some tolerance, but big gaps are issues
            gaps = diffs[diffs > pd.Timedelta(hours=1.1)]
            if not gaps.empty:
                issues.append(f"Found {len(gaps)} time gaps > 1.1 hours")
                issues.append(f"  Largest gap: {gaps.max()}")
        except Exception as e:
            issues.append(f"Timestamp parsing error: {e}")

    if issues:
        print("  [ISSUES FOUND]")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("  [OK] Data looks clean.")

def main():
    path = Path(DATA_DIR)
    if not path.exists():
        print(f"Directory {DATA_DIR} not found.")
        return

    files = list(path.glob("*.csv")) + list(path.glob("*.parquet"))
    if not files:
        print(f"No CSV or Parquet files found in {DATA_DIR}")
        return

    print(f"Found {len(files)} files. Starting validation...")
    for f in files:
        check_file(f)
    
    print("\nValidation complete.")

if __name__ == "__main__":
    main()
