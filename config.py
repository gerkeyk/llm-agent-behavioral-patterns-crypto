# config.py

import os
from datetime import datetime

# === TRADING ===
TRADING_SYMBOLS = ["BTCUSDC", "ETHUSDC", "SOLUSDC", "XRPUSDC", "DOGEUSDC"]
QUOTE_ASSET = "USDC"
CANDLE_INTERVAL = "5m"
STARTING_USDC = 1000.0
MIN_TRADE_USDC = 1.0  # Minimum trade size
FEE_RATE = 0.001  # 0.1%

# === 10 TEST PERIODS ===
TEST_PERIODS = [
    {"id": 1, "name": "01_jan_2021_early_bull", "start": "2021-01-01", "end": "2021-01-14"},
    {"id": 2, "name": "02_jun_2021_post_crash", "start": "2021-06-01", "end": "2021-06-14"},
    {"id": 3, "name": "03_nov_2021_ath_peak", "start": "2021-11-08", "end": "2021-11-21"},
    {"id": 4, "name": "04_apr_2022_declining", "start": "2022-04-01", "end": "2022-04-14"},
    {"id": 5, "name": "05_aug_2022_deep_bear", "start": "2022-08-15", "end": "2022-08-28"},
    {"id": 6, "name": "06_jan_2023_bear_bottom", "start": "2023-01-01", "end": "2023-01-14"},
    {"id": 7, "name": "07_jun_2023_recovery", "start": "2023-06-01", "end": "2023-06-14"},
    {"id": 8, "name": "08_oct_2023_sideways", "start": "2023-10-15", "end": "2023-10-28"},
    {"id": 9, "name": "09_mar_2024_etf_rally", "start": "2024-03-01", "end": "2024-03-14"},
    {"id": 10, "name": "10_aug_2024_consolidation", "start": "2024-08-01", "end": "2024-08-14"},
]

# === AI ===
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_SYSTEM_PROMPT_ID = "pmpt_695c32c73a308195bb823853d319968c0ae440f3dfb5a08d"
OPENAI_TEMPERATURE = 0.4
OPENAI_MAX_TOKENS = 100
OPENAI_MAX_RETRIES = 5
OPENAI_RETRY_DELAY = 2  # seconds

# === PATHS ===
DATA_DIR = "data"
HISTORICAL_DIR = f"{DATA_DIR}/historical"
CHECKPOINT_DIR = f"{DATA_DIR}/checkpoints"
DB_PATH = f"{DATA_DIR}/backtest_results.db"
LOG_FILE = f"{DATA_DIR}/backtest.log"

# Create directories
for d in [DATA_DIR, HISTORICAL_DIR, CHECKPOINT_DIR]:
    os.makedirs(d, exist_ok=True)