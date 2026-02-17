
import os
import sys
from dotenv import load_dotenv

# Load env vars first
load_dotenv()

from ai_client import client, OPENAI_MODEL, OPENAI_TEMPERATURE, OPENAI_MAX_TOKENS

def test_api_call():
    print("Testing OpenAI API call...")
    print(f"Model: {OPENAI_MODEL}")
    
    system_prompt = "You are a crypto trading bot. Analyze the market data and portfolio state to make a profitable trading decision. You MUST respond with a JSON object containing 'action' (BUY, SELL, HOLD) and 'amount' (float, optional)."
    
    user_prompt = """SYMBOL: BTCUSDC
MARKET DATA:
- Price: $50000.00
- 1H Change: +0.50%
- RSI(14): 55.0

YOUR PORTFOLIO:
- Available USDC: $1000.00
- BTC Holdings: 0.000000

AVAILABLE ACTIONS: HOLD, BUY (max $1000.00)

Respond ONLY with JSON."""

    try:
        print("\nSending request...")
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {"role": "user", "content": user_prompt}
            ],
            temperature=OPENAI_TEMPERATURE,
            max_tokens=OPENAI_MAX_TOKENS,
            response_format={"type": "json_object"}
        )
        print("\nSUCCESS!")
        print(response.choices[0].message.content)
        
    except Exception as e:
        print("\nFAILED!")
        print(f"Error type: {type(e)}")
        print(f"Error message: {e}")
        
        # Try to inspect specific OpenAI error attributes if available
        if hasattr(e, 'response'):
            print(f"\nResponse Code: {e.response.status_code}")
            print(f"Response Headers: {e.response.headers}")
            print(f"Response Content: {e.response.content}")
        if hasattr(e, 'body'):
            print(f"Body: {e.body}")

if __name__ == "__main__":
    test_api_call()
