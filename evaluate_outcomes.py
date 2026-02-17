#!/usr/bin/env python3
"""
Outcome Evaluator - Retrospectively evaluates AI trading decisions.

This script:
1. Fetches historical price data for each decision's timestamp
2. Looks ahead 5min and 1h to determine actual price movement
3. Updates the was_correct field based on whether the AI's action was optimal
4. Updates price_5min_later, price_1h_later, and price_direction fields

Logic:
- BUY decision: correct if price went up (price_1h_later > current_price)
- SELL decision: correct if price went down (price_1h_later < current_price)
- HOLD decision: correct if price change was small (<2% either direction)
"""

import sqlite3
import pandas as pd
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys

class OutcomeEvaluator:
    def __init__(self, db_path: str, historical_data_dir: str):
        self.db_path = db_path
        self.historical_data_dir = Path(historical_data_dir)
        self.price_cache = {}  # Cache loaded parquet files

    def load_price_data(self, symbol: str) -> pd.DataFrame:
        """Load and cache historical price data for a symbol."""
        if symbol in self.price_cache:
            return self.price_cache[symbol]

        # Find ALL parquet files for this symbol
        parquet_files = sorted(self.historical_data_dir.glob(f"*{symbol}*.parquet"))
        if not parquet_files:
            print(f"Warning: No parquet file found for {symbol}")
            return None

        # Load and concatenate all files for this symbol
        dfs = []
        for pf in parquet_files:
            df = pd.read_parquet(pf)
            dfs.append(df)

        # Concatenate all dataframes
        df = pd.concat(dfs, ignore_index=True)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp').drop_duplicates('timestamp').reset_index(drop=True)

        self.price_cache[symbol] = df
        print(f"Loaded {len(df)} candles for {symbol} (from {len(parquet_files)} files)")
        return df

    def get_future_prices(self, df: pd.DataFrame, timestamp: datetime, current_price: float):
        """Get prices 5min and 1h after the given timestamp."""
        # Find the row matching this timestamp
        idx = df[df['timestamp'] == timestamp].index
        if len(idx) == 0:
            return None, None

        idx = idx[0]

        # 5min later (next candle)
        price_5min = df.loc[idx + 1, 'close'] if idx + 1 < len(df) else None

        # 1h later (12 candles ahead for 5min candles)
        price_1h = df.loc[idx + 12, 'close'] if idx + 12 < len(df) else None

        return price_5min, price_1h

    def evaluate_decision(self, action: str, current_price: float, future_price: float) -> tuple:
        """
        Determine if a decision was correct based on future price movement.
        Returns: (was_correct: bool, direction: str)
        """
        if future_price is None:
            return None, None

        price_change_pct = ((future_price - current_price) / current_price) * 100

        # Determine direction
        if price_change_pct > 0.5:
            direction = "UP"
        elif price_change_pct < -0.5:
            direction = "DOWN"
        else:
            direction = "FLAT"

        # Evaluate correctness
        if action == "BUY":
            was_correct = direction == "UP"
        elif action == "SELL":
            was_correct = direction == "DOWN"
        elif action == "HOLD":
            # HOLD is correct if price didn't move much, or if moving would have been bad
            # We'll consider HOLD correct if abs(price_change) < 2%
            was_correct = abs(price_change_pct) < 2.0
        else:
            was_correct = False

        return was_correct, direction

    def process_decisions(self, limit: int = None):
        """Process all decisions that need outcome evaluation."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        # Get decisions needing evaluation
        query = """
            SELECT id, timestamp, symbol, action, current_price
            FROM ai_decisions
            WHERE was_correct IS NULL
            ORDER BY id
        """
        if limit:
            query += f" LIMIT {limit}"

        cursor = conn.execute(query)
        decisions = cursor.fetchall()

        total = len(decisions)
        print(f"Found {total} decisions to evaluate")

        if total == 0:
            print("No decisions need evaluation. Database is up to date!")
            conn.close()
            return

        updated = 0
        failed = 0

        for i, decision in enumerate(decisions):
            if (i + 1) % 1000 == 0:
                print(f"Progress: {i+1}/{total} ({updated} updated, {failed} failed)")

            dec_id = decision['id']
            symbol = decision['symbol']
            action = decision['action']
            timestamp = pd.to_datetime(decision['timestamp'])
            current_price = decision['current_price']

            # Load price data for this symbol
            df = self.load_price_data(symbol)
            if df is None:
                failed += 1
                continue

            # Get future prices
            price_5min, price_1h = self.get_future_prices(df, timestamp, current_price)

            if price_1h is None:
                # Can't evaluate if we don't have future data
                failed += 1
                continue

            # Evaluate decision (use 1h price for correctness evaluation)
            was_correct, direction = self.evaluate_decision(action, current_price, price_1h)

            if was_correct is None:
                failed += 1
                continue

            # Update database
            conn.execute('''
                UPDATE ai_decisions
                SET price_5min_later = ?,
                    price_1h_later = ?,
                    price_direction = ?,
                    was_correct = ?
                WHERE id = ?
            ''', (price_5min, price_1h, direction, 1 if was_correct else 0, dec_id))

            updated += 1

        conn.commit()
        conn.close()

        print(f"\n{'='*60}")
        print(f"Evaluation Complete!")
        print(f"  Total Decisions: {total}")
        print(f"  Successfully Updated: {updated}")
        print(f"  Failed: {failed}")
        print(f"{'='*60}")

        # Show summary stats
        if updated > 0:
            self.print_summary_stats()
        
        # Always update session win rates to ensure DB is consistent
        self.update_session_win_rates()

    def update_session_win_rates(self):
        """Update the win_rate column in backtest_sessions table."""
        conn = sqlite3.connect(self.db_path)
        
        # Get win rates by session
        cursor = conn.execute("""
            SELECT 
                session_id,
                COUNT(*) as total,
                SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END) as correct
            FROM ai_decisions 
            WHERE was_correct IS NOT NULL
            GROUP BY session_id
        """)
        
        rows = cursor.fetchall()
        print(f"\nUpdating win rates for {len(rows)} sessions...")
        
        for row in rows:
            session_id = row[0]
            total = row[1]
            correct = row[2]
            win_rate = correct / total if total > 0 else 0.0
            
            conn.execute("""
                UPDATE backtest_sessions 
                SET win_rate = ? 
                WHERE id = ?
            """, (win_rate, session_id))
            print(f"  Session {session_id}: {win_rate:.3f} ({correct}/{total})")
            
        conn.commit()
        conn.close()

    def print_summary_stats(self):
        """Print summary statistics after evaluation."""
        conn = sqlite3.connect(self.db_path)

        # Overall win rate
        cursor = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END) as correct,
                ROUND(AVG(CASE WHEN was_correct IS NOT NULL THEN was_correct ELSE NULL END) * 100, 2) as win_rate_pct
            FROM ai_decisions
            WHERE was_correct IS NOT NULL
        """)
        row = cursor.fetchone()
        print(f"\nOVERALL STATISTICS:")
        print(f"  Evaluated Decisions: {row[0]}")
        print(f"  Correct: {row[1]}")
        print(f"  Win Rate: {row[2]}%")

        # By action
        cursor = conn.execute("""
            SELECT
                action,
                COUNT(*) as total,
                SUM(was_correct) as correct,
                ROUND(AVG(was_correct) * 100, 2) as win_rate_pct
            FROM ai_decisions
            WHERE was_correct IS NOT NULL
            GROUP BY action
        """)

        print(f"\nBY ACTION:")
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[3]}% ({row[2]}/{row[1]})")

        conn.close()

def main():
    parser = argparse.ArgumentParser(
        description="Evaluate AI trading decision outcomes retrospectively"
    )
    parser.add_argument(
        "--db",
        default="data/backtest_results.db",
        help="Path to SQLite database"
    )
    parser.add_argument(
        "--data-dir",
        default="data/historical",
        help="Directory containing historical parquet files"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of decisions to evaluate (for testing)"
    )

    args = parser.parse_args()

    # Validate paths
    if not Path(args.db).exists():
        print(f"Error: Database not found at {args.db}")
        sys.exit(1)

    if not Path(args.data_dir).exists():
        print(f"Error: Data directory not found at {args.data_dir}")
        sys.exit(1)

    print("AI Trading Decision Outcome Evaluator")
    print("="*60)

    evaluator = OutcomeEvaluator(args.db, args.data_dir)
    evaluator.process_decisions(limit=args.limit)

if __name__ == "__main__":
    main()
