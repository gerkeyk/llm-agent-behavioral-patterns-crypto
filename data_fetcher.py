# data_fetcher.py

from binance.client import Client
import pandas as pd
from datetime import datetime, timedelta
import os
import time

class DataFetcher:
    def __init__(self):
        # No API key needed for public historical data
        self.client = Client("", "")
        self.cache_dir = "data/historical"
        os.makedirs(self.cache_dir, exist_ok=True)

    def fetch(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """Fetch historical OHLCV data for a symbol"""
        cache_file = f"{self.cache_dir}/{symbol}_{start}_{end}.parquet"

        # Return cached data if available
        if os.path.exists(cache_file):
            print(f"  Loading cached {symbol}")
            return pd.read_parquet(cache_file)

        print(f"  Fetching {symbol} from Binance ({start} to {end})...")

        all_klines = []
        current = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)

        while current < end_dt:
            try:
                klines = self.client.get_historical_klines(
                    symbol=symbol,
                    interval="5m",
                    start_str=current.strftime("%d %b %Y"),
                    end_str=end_dt.strftime("%d %b %Y"),
                    limit=1000
                )
                if not klines:
                    break

                all_klines.extend(klines)
                last_timestamp = klines[-1][0]
                current = datetime.fromtimestamp(last_timestamp / 1000) + timedelta(minutes=5)

                # Rate limiting
                time.sleep(0.3)

            except Exception as e:
                print(f"    Error fetching {symbol}: {e}")
                break

        if not all_klines:
            print(f"    No data retrieved for {symbol}")
            return pd.DataFrame()

        # Parse into DataFrame
        df = pd.DataFrame(all_klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_vol', 'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])

        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        # Convert price columns to float
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)

        # Keep only essential columns
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]

        # Save to cache
        df.to_parquet(cache_file)
        print(f"    Cached {len(df)} candles")

        return df

    def fetch_all(self, start: str, end: str, symbols: list) -> dict:
        """Fetch data for all symbols in the list"""
        return {symbol: self.fetch(symbol, start, end) for symbol in symbols}
