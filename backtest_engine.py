# backtest_engine.py

import time
from datetime import datetime
from typing import Dict, List
import logging

from config import TRADING_SYMBOLS, STARTING_USDC, TEST_PERIODS, LOG_FILE
from data_fetcher import DataFetcher
from fear_greed import FearGreed
from portfolio import Portfolio
from ai_client import get_ai_decision
from indicators import calculate as calculate_indicators
from database import Database
from checkpoint import Checkpoint

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class BacktestEngine:
    def __init__(self):
        self.db = Database()
        self.fetcher = DataFetcher()
        self.fg = FearGreed()
    
    def run_period(self, period: dict) -> dict:
        """Run backtest for a single period with checkpointing."""
        
        logger.info(f"{'='*60}")
        logger.info(f"PERIOD: {period['name']}")
        logger.info(f"{period['start']} → {period['end']}")
        logger.info(f"{'='*60}")
        
        # Create or resume session
        session_id = self.db.create_session(period)
        if session_id is None:
            return None  # Already completed
        
        # Check for checkpoint
        checkpoint = Checkpoint.load(session_id)
        if checkpoint:
            logger.info(f"Resuming from candle {checkpoint['candle_idx']}")
            portfolio = Portfolio.from_checkpoint(checkpoint['portfolio'])
            start_idx = checkpoint['candle_idx'] + 1
            stats = checkpoint['stats']
        else:
            portfolio = Portfolio.new()
            start_idx = 0
            stats = {'buy': 0, 'sell': 0, 'hold': 0, 'executed': 0, 'skipped': 0}
        
        # Fetch data
        logger.info("Fetching historical data...")
        raw_data = self.fetcher.fetch_all(period['start'], period['end'], TRADING_SYMBOLS)
        data = {}
        
        # Verify all symbols have data
        for symbol, df in raw_data.items():
            if len(df) > 0:
                data[symbol] = df
            else:
                logger.warning(f"No data for {symbol}, skipping symbol")
        
        self.fg.fetch_range(period['start'], period['end'])
        
        # Get timestamps from reference symbol
        ref_symbol = TRADING_SYMBOLS[0]
        timestamps = data[ref_symbol]['timestamp'].tolist()
        total_candles = len(timestamps)
        
        # Track starting prices for benchmark
        start_prices = {s: data[s].iloc[0]['close'] for s in TRADING_SYMBOLS if s in data}
        
        # Process candles
        logger.info(f"Processing {total_candles - start_idx} candles...")
        
        pending_outcomes = []  # Track decisions needing outcome updates
        
        for i in range(start_idx, total_candles):
            ts = timestamps[i]
            
            # Progress logging
            if i % 100 == 0:
                prices = {s: data[s].iloc[min(i, len(data[s])-1)]['close'] 
                         for s in TRADING_SYMBOLS if s in data}
                value = portfolio.get_total_value(prices)
                logger.info(f"Progress: {i}/{total_candles} | Portfolio: ${value:.2f}")
            
            # Get current prices for all symbols
            current_prices = {}
            for symbol in TRADING_SYMBOLS:
                if symbol not in data:
                    continue
                df = data[symbol]
                mask = df['timestamp'] == ts
                if mask.any():
                    current_prices[symbol] = df.loc[mask.index[0], 'close']
            
            # Fear & Greed
            fg_val = self.fg.get(ts)
            regime = self.fg.classify(fg_val)
            
            # ============================================ 
            # PROCESS SYMBOLS SEQUENTIALLY (CRITICAL FIX)
            # ============================================ 
            for symbol in TRADING_SYMBOLS:
                if symbol not in data or symbol not in current_prices:
                    continue
                
                df = data[symbol]
                mask = df['timestamp'] == ts
                if not mask.any():
                    continue
                
                idx = mask.idxmax()
                
                # Calculate indicators
                ind = calculate_indicators(df, idx)
                if not ind:
                    continue
                
                # Check what trades are possible BEFORE calling AI
                trade_check = portfolio.can_trade(symbol)
                
                # Get portfolio state for AI
                port_state = portfolio.get_state_for_ai(symbol, ind['current_price'], current_prices)
                
                # Get AI decision
                decision = get_ai_decision(
                    symbol, ind, port_state,
                    can_buy=trade_check['can_buy'],
                    can_sell=trade_check['can_sell']
                )
                
                # Validate the decision
                validation = {'valid': True, 'note': 'OK'}
                
                if decision['action'] == 'BUY':
                    validation = portfolio.validate_buy(decision['amount'])
                    stats['buy'] += 1
                elif decision['action'] == 'SELL':
                    validation = portfolio.validate_sell(symbol, decision['amount'])
                    stats['sell'] += 1
                else:
                    stats['hold'] += 1
                
                # Log decision to database
                decision_id = self.db.log_decision(
                    session_id=session_id,
                    timestamp=ts.isoformat(),
                    symbol=symbol,
                    action=decision['action'],
                    requested_amount=decision['amount'],
                    indicators=ind,
                    portfolio=port_state,
                    validation=validation,
                    fear_greed=fg_val,
                    market_regime=regime,
                    api_stats=decision
                )
                
                # Track for outcome update
                pending_outcomes.append({
                    'decision_id': decision_id,
                    'idx': idx,
                    'symbol': symbol,
                    'action': decision['action'],
                    'current_price': ind['current_price']
                })
                
                # Execute trade if valid
                trade_result = None
                
                if decision['action'] == 'BUY' and validation['valid']:
                    trade_result = portfolio.execute_buy(
                        symbol, validation['amount'], ind['current_price']
                    )
                elif decision['action'] == 'SELL' and validation['valid']:
                    trade_result = portfolio.execute_sell(
                        symbol, validation['amount'], ind['current_price']
                    )
                
                if trade_result:
                    asset = symbol.replace("USDC", "")
                    self.db.log_trade(
                        decision_id, session_id, ts.isoformat(), trade_result,
                        {'usdc': portfolio.usdc, 'asset': portfolio.holdings.get(asset, 0)}
                    )
                    stats['executed'] += 1
                    logger.debug(f"{ts} | {symbol} | {trade_result['side']} | {trade_result['quantity']} @ {trade_result['price']}")
                
                elif decision['action'] != 'HOLD' and not validation['valid']:
                     self.db.mark_skipped(decision_id, validation['note'])

            # Checkpoint
            Checkpoint.save(session_id, period['id'], i, portfolio.to_checkpoint(), stats)
            
            # Snapshot every hour (approx 12 candles)
            if i % 12 == 0:
                 self.db.save_snapshot(session_id, ts.isoformat(), portfolio, current_prices, fg_val)
        
        # --- End of candle loop ---
        
        Checkpoint.delete(session_id)
        
        # Final stats
        final_value = portfolio.get_total_value(current_prices) if current_prices else portfolio.usdc
        return_pct = (final_value - 1000) / 1000 * 100
        
        # Benchmark return
        mkt_return = 0.0
        if ref_symbol in start_prices and ref_symbol in current_prices:
            start_p = start_prices[ref_symbol]
            end_p = current_prices[ref_symbol]
            mkt_return = (end_p - start_p) / start_p * 100
            
        final_stats = {
            'ending_usdc': round(portfolio.usdc, 2),
            'ending_value': round(final_value, 2),
            'total_return': round(return_pct, 2),
            'total_decisions': stats['buy'] + stats['sell'] + stats['hold'],
            'buy_count': stats['buy'],
            'sell_count': stats['sell'],
            'hold_count': stats['hold'],
            'executed_trades': stats['executed'],
            'win_rate': 0.0, 
            'avg_fear_greed': 50.0, 
            'market_return': round(mkt_return, 2)
        }
        
        self.db.complete_session(session_id, final_stats)
        logger.info(f"Period {period['name']} complete. Return: {return_pct:.2f}%")
        
        return final_stats

    def run_all(self):
        """Run backtest for all defined periods."""
        results = []
        logger.info(f"Starting backtest for 5 (out of {len(TEST_PERIODS)}) periods")
        for period in TEST_PERIODS[:5]:
            try:
                res = self.run_period(period)
                if res:
                    results.append(res)
            except Exception as e:
                logger.error(f"Error in period {period['name']}: {e}", exc_info=True)
        return results