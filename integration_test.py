#!/usr/bin/env python3
"""integration_test.py - Test all components together"""

import sys
sys.path.insert(0, '.')

from portfolio import Portfolio
from database import Database
from checkpoint import Checkpoint
from config import TRADING_SYMBOLS, STARTING_USDC, MIN_TRADE_USDC
import os

def test_full_flow():
    print("="*60)
    print("INTEGRATION TEST")
    print("="*60)
    
    errors = []
    
    # 1. Portfolio validation
    print("\n1. Testing Portfolio Validation...")
    try:
        p = Portfolio.new()
        assert p.usdc == STARTING_USDC
        
        # Can't sell without holdings
        v = p.validate_sell("BTCUSDC", 1.0)
        assert v['valid'] == False
        
        # BUY capped at balance
        v = p.validate_buy(2000)
        assert v['amount'] <= p.usdc
        
        print("   ✅ Portfolio validation OK")
    except Exception as e:
        errors.append(f"Portfolio: {e}")
        print(f"   ❌ Portfolio validation FAILED: {e}")
    
    # 2. Sequential balance updates
    print("\n2. Testing Sequential Processing...")
    try:
        p = Portfolio.new()
        
        # Buy on first symbol
        p.execute_buy("BTCUSDC", 600, 50000)
        remaining_after_1 = p.usdc
        
        # Second symbol should see reduced balance
        assert p.usdc < STARTING_USDC
        
        # Buy on second symbol
        p.execute_buy("ETHUSDC", 600, 3000)  # Will be capped
        
        # Should have less than before
        assert p.usdc < remaining_after_1
        
        print("   ✅ Sequential processing OK")
    except Exception as e:
        errors.append(f"Sequential: {e}")
        print(f"   ❌ Sequential processing FAILED: {e}")
    
    # 3. Database
    print("\n3. Testing Database...")
    try:
        db = Database('data/test_db.db')
        
        # Create session
        session_id = db.create_session({
            'id': 999, 'name': 'test', 
            'start': '2024-01-01', 'end': '2024-01-14'
        })
        
        assert session_id is not None
        print("   ✅ Database OK")
        
        # Cleanup
        os.remove('data/test_db.db')
    except Exception as e:
        errors.append(f"Database: {e}")
        print(f"   ❌ Database FAILED: {e}")
    
    # 4. Checkpoint
    print("\n4. Testing Checkpoint...")
    try:
        # save(session_id, period_id, candle_idx, portfolio_data, stats)
        Checkpoint.save(888, 1, 50, {'usdc': 900}, {'buy': 3})
        data = Checkpoint.load(888)
        assert data['candle_idx'] == 50
        Checkpoint.delete(888)
        print("   ✅ Checkpoint OK")
    except Exception as e:
        errors.append(f"Checkpoint: {e}")
        print(f"   ❌ Checkpoint FAILED: {e}")
    
    # Summary
    print("\n" + "="*60)
    if errors:
        print(f"❌ FAILED - {len(errors)} error(s):")
        for e in errors:
            print(f"   - {e}")
        return False
    else:
        print("✅ ALL TESTS PASSED")
        return True

if __name__ == "__main__":
    success = test_full_flow()
    sys.exit(0 if success else 1)
