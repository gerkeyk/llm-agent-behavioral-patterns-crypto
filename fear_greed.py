# fear_greed.py

import requests
import json
import os
from datetime import datetime

class FearGreed:
    def __init__(self):
        self.cache_file = "data/historical/fear_greed.json"
        self.cache = self._load()

    def _load(self):
        """Load cached Fear & Greed data"""
        if os.path.exists(self.cache_file):
            with open(self.cache_file) as f:
                return json.load(f)
        return {}

    def _save(self):
        """Save cache to disk"""
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f)

    def fetch_range(self, start: str, end: str):
        """Fetch Fear & Greed Index for a date range"""
        days = (datetime.strptime(end, "%Y-%m-%d") - datetime.strptime(start, "%Y-%m-%d")).days + 30
        try:
            r = requests.get(f"https://api.alternative.me/fng/?limit={days}&date_format=world", timeout=30)
            if r.status_code == 200:
                for item in r.json()['data']:
                    self.cache[item['timestamp']] = int(item['value'])
                self._save()
                print(f"  Fetched Fear & Greed data: {len(r.json()['data'])} days")
        except Exception as e:
            print(f"  Fear & Greed fetch error: {e}")

    def get(self, ts: datetime) -> int:
        """Get Fear & Greed Index for a specific timestamp"""
        key = ts.strftime("%d-%m-%Y")
        return self.cache.get(key, 50)

    def classify(self, val: int) -> str:
        """Classify Fear & Greed value into regime"""
        if val < 25:
            return "PANIC"
        if val < 40:
            return "FEAR"
        if val > 75:
            return "EUPHORIA"
        if val > 60:
            return "GREED"
        return "NEUTRAL"
