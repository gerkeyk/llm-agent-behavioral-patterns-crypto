import json
import time
import math
from openai import OpenAI
from .base import BaseAIProvider
from config import (
    OPENAI_MODEL, OPENAI_TEMPERATURE,
    OPENAI_MAX_TOKENS, OPENAI_MAX_RETRIES, OPENAI_RETRY_DELAY
)

class OpenAIProvider(BaseAIProvider):
    def __init__(self):
        self.client = OpenAI()

    def _create_prompt(self, symbol: str, indicators: dict, portfolio: dict, 
                      can_buy: bool, can_sell: bool) -> str:
        """
        Create prompt with FULL portfolio state and available actions.
        """
        # Helper to sanitize values
        def safe(val):
            if val is None: return 0.0
            try:
                f = float(val)
                if math.isnan(f) or math.isinf(f):
                    return 0.0
                return f
            except:
                return 0.0

        # Sanitize inputs
        ind = {k: safe(v) for k, v in indicators.items()}
        port = {k: safe(v) for k, v in portfolio.items()}
        
        asset = symbol.replace("USDC", "")
        
        # Build available actions
        actions = ["HOLD"]
        if can_buy:
            actions.append(f"BUY (max ${port['usdc_balance']:.2f})")
        if can_sell:
            actions.append(f"SELL (max {port['asset_balance']:.6f} {asset})")
        
        return f"""SYMBOL: {symbol}

MARKET DATA:
- Price: ${ind['current_price']:.6f}
- 1H Change: {ind['price_change_1h']:+.2f}%
- 24H Change: {ind['price_change_24h']:+.2f}%
- EMA(12): ${ind['ema_12']:.6f}
- EMA(26): ${ind['ema_26']:.6f}
- RSI(14): {ind['rsi_14']:.1f}
- Bollinger Position: {ind['bb_position']:.2f}
- Volume Ratio: {ind['volume_ratio']:.2f}x

YOUR PORTFOLIO:
- Available USDC: ${port['usdc_balance']:.2f}
- {asset} Holdings: {port['asset_balance']:.6f} (worth ${port['asset_value']:.2f})
- Total Portfolio Value: ${port['total_value']:.2f}

AVAILABLE ACTIONS: {', '.join(actions)}

Respond ONLY with JSON. Do not exceed available balances."""

    def get_decision(self, symbol: str, indicators: dict, portfolio: dict, 
                     can_buy: bool, can_sell: bool) -> dict:
        """
        Call OpenAI API with retries.
        """
        prompt = self._create_prompt(symbol, indicators, portfolio, can_buy, can_sell)
        
        for attempt in range(OPENAI_MAX_RETRIES):
            start_time = time.time()
            
            try:
                response = self.client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a crypto trading bot. Analyze the market data and portfolio state to make a profitable trading decision. You MUST respond with a JSON object containing 'action' (BUY, SELL, HOLD) and 'amount' (float, optional)."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=OPENAI_TEMPERATURE,
                    max_tokens=OPENAI_MAX_TOKENS,
                    response_format={"type": "json_object"}
                )
                
                latency_ms = int((time.time() - start_time) * 1000)
                content = response.choices[0].message.content
                decision = json.loads(content)
                
                # Parse and validate
                action = decision.get('action', 'HOLD').upper()
                if action not in ['BUY', 'SELL', 'HOLD']:
                    action = 'HOLD'
                
                # If action not possible, force HOLD
                if action == 'BUY' and not can_buy:
                    action = 'HOLD'
                if action == 'SELL' and not can_sell:
                    action = 'HOLD'
                
                amount = decision.get('amount')
                if amount is not None:
                    try:
                        amount = float(amount)
                        if amount <= 0:
                            amount = None
                    except:
                        amount = None
                
                return {
                    'action': action,
                    'amount': amount,
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'latency_ms': latency_ms,
                    'success': True
                }
            
            except Exception as e:
                print(f"API error (attempt {attempt + 1}/{OPENAI_MAX_RETRIES}): {e}")
                # Log the problematic prompt for debugging
                if "400" in str(e):
                    print(f"DEBUG - FAILED PROMPT:\n{prompt}\n-------------------")
                
                if attempt < OPENAI_MAX_RETRIES - 1:
                    time.sleep(OPENAI_RETRY_DELAY * (attempt + 1))
                else:
                    return {
                        'action': 'HOLD',
                        'amount': None,
                        'prompt_tokens': 0,
                        'completion_tokens': 0,
                        'latency_ms': 0,
                        'success': False,
                        'error': str(e)
                    }
        
        return {
            'action': 'HOLD',
            'amount': None,
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'latency_ms': 0,
            'success': False
        }
