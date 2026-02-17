# indicators.py

import pandas as pd
import numpy as np
from typing import Optional, Dict

def calculate(df: pd.DataFrame, idx: int) -> Optional[Dict]:
    """Calculate technical indicators up to index idx"""
    # Need at least 30 candles for all indicators
    data = df.iloc[:idx+1]
    if len(data) < 30:
        return None

    close = data['close']
    price = close.iloc[-1]

    # EMAs
    ema_12 = close.ewm(span=12, adjust=False).mean().iloc[-1]
    ema_26 = close.ewm(span=26, adjust=False).mean().iloc[-1]

    # RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    
    loss_val = loss.iloc[-1]
    gain_val = gain.iloc[-1]
    
    if loss_val > 0:
        rs = gain_val / loss_val
        rsi = 100 - (100 / (1 + rs))
    else:
        # If no loss, RSI is 100 (if there was gain) or 50 (flat)
        rsi = 100.0 if gain_val > 0 else 50.0

    # Bollinger Bands
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std

    bb_range = bb_upper.iloc[-1] - bb_lower.iloc[-1]
    if bb_range > 0:
        bb_position = (price - bb_lower.iloc[-1]) / bb_range
    else:
        bb_position = 0.5

    # Volume ratio
    vol_sma = data['volume'].rolling(20).mean().iloc[-1]
    if vol_sma > 0:
        volume_ratio = data['volume'].iloc[-1] / vol_sma
    else:
        volume_ratio = 1.0

    # Price changes
    if len(close) >= 12:
        price_1h_ago = close.iloc[-12]
    else:
        price_1h_ago = close.iloc[0]

    if len(close) >= 288:
        price_24h_ago = close.iloc[-288]
    else:
        price_24h_ago = close.iloc[0]

    if price_1h_ago > 0:
        price_change_1h = (price - price_1h_ago) / price_1h_ago * 100
    else:
        price_change_1h = 0.0
        
    if price_24h_ago > 0:
        price_change_24h = (price - price_24h_ago) / price_24h_ago * 100
    else:
        price_change_24h = 0.0

    return {
        'current_price': round(price, 6),
        'price_change_1h': round(price_change_1h, 2),
        'price_change_24h': round(price_change_24h, 2),
        'ema_12': round(ema_12, 6),
        'ema_26': round(ema_26, 6),
        'rsi_14': round(rsi, 1),
        'bb_position': round(bb_position, 2),
        'volume_ratio': round(volume_ratio, 2)
    }
