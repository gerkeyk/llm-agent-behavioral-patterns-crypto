# database.py

import sqlite3
from datetime import datetime
from contextlib import contextmanager
import json
import os
from config import DB_PATH

class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()
    
    @contextmanager
    def _connection(self):
        """Context manager for database connections with auto-commit."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _init_db(self):
        """Initialize database schema."""
        with self._connection() as conn:
            conn.executescript('''
                -- Backtest sessions
                CREATE TABLE IF NOT EXISTS backtest_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    period_id INTEGER NOT NULL,
                    period_name VARCHAR(50) NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    started_at DATETIME NOT NULL,
                    completed_at DATETIME,
                    status VARCHAR(20) DEFAULT 'running',
                    starting_usdc REAL NOT NULL DEFAULT 1000.0,
                    ending_usdc REAL,
                    ending_portfolio_value REAL,
                    total_return_percent REAL,
                    total_decisions INTEGER DEFAULT 0,
                    buy_count INTEGER DEFAULT 0,
                    sell_count INTEGER DEFAULT 0,
                    hold_count INTEGER DEFAULT 0,
                    executed_trades INTEGER DEFAULT 0,
                    win_rate REAL,
                    avg_fear_greed REAL,
                    market_return_percent REAL,
                    last_processed_idx INTEGER DEFAULT 0,
                    UNIQUE(period_id)
                );

                -- AI decisions (FIXED: was_correct as INTEGER)
                CREATE TABLE IF NOT EXISTS ai_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    timestamp DATETIME NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    
                    -- AI output
                    action VARCHAR(10) NOT NULL,
                    requested_amount REAL,
                    
                    -- Validation (NEW)
                    amount_valid INTEGER DEFAULT 1,
                    validation_note TEXT,
                    
                    -- Market data
                    current_price REAL NOT NULL,
                    price_change_1h REAL,
                    price_change_24h REAL,
                    ema_12 REAL,
                    ema_26 REAL,
                    rsi_14 REAL,
                    bb_position REAL,
                    volume_ratio REAL,
                    
                    -- Portfolio state AT DECISION TIME
                    usdc_balance REAL NOT NULL,
                    asset_balance REAL NOT NULL,
                    asset_value_usdc REAL NOT NULL,
                    total_portfolio_value REAL NOT NULL,
                    
                    -- Outcome (FIXED: INTEGER not BLOB)
                    price_5min_later REAL,
                    price_1h_later REAL,
                    price_direction VARCHAR(10),
                    was_correct INTEGER,
                    
                    -- Context
                    fear_greed_index INTEGER,
                    market_regime VARCHAR(20),
                    
                    -- Execution
                    was_executed INTEGER DEFAULT 0,
                    execution_price REAL,
                    execution_quantity REAL,
                    execution_fee REAL,
                    skipped_reason TEXT,
                    
                    -- API
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    api_latency_ms INTEGER,
                    
                    FOREIGN KEY (session_id) REFERENCES backtest_sessions(id)
                );

                -- Executed trades
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    decision_id INTEGER NOT NULL,
                    session_id INTEGER NOT NULL,
                    timestamp DATETIME NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    side VARCHAR(10) NOT NULL,
                    quantity REAL NOT NULL,
                    price REAL NOT NULL,
                    value_usdc REAL NOT NULL,
                    fee_usdc REAL NOT NULL,
                    usdc_after REAL NOT NULL,
                    asset_after REAL NOT NULL,
                    FOREIGN KEY (decision_id) REFERENCES ai_decisions(id),
                    FOREIGN KEY (session_id) REFERENCES backtest_sessions(id)
                );

                -- Portfolio snapshots
                CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    timestamp DATETIME NOT NULL,
                    usdc_balance REAL NOT NULL,
                    total_value REAL NOT NULL,
                    pnl_percent REAL,
                    fear_greed_index INTEGER,
                    holdings_json TEXT,
                    FOREIGN KEY (session_id) REFERENCES backtest_sessions(id)
                );

                -- Indexes for performance
                CREATE INDEX IF NOT EXISTS idx_decisions_session ON ai_decisions(session_id);
                CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON ai_decisions(timestamp);
                CREATE INDEX IF NOT EXISTS idx_trades_session ON trades(session_id);
                CREATE INDEX IF NOT EXISTS idx_snapshots_session ON portfolio_snapshots(session_id);
            ''')
    
    def create_session(self, period: dict) -> int:
        """Create new backtest session. Returns session_id."""
        with self._connection() as conn:
            # Check if session exists (for resume)
            existing = conn.execute(
                'SELECT id, status FROM backtest_sessions WHERE period_id = ?',
                (period['id'],)
            ).fetchone()
            
            if existing:
                if existing['status'] == 'completed':
                    print(f"Period {period['name']} already completed, skipping.")
                    return None
                else:
                    print(f"Resuming period {period['name']} from checkpoint.")
                    return existing['id']
            
            cursor = conn.execute('''
                INSERT INTO backtest_sessions 
                (period_id, period_name, start_date, end_date, started_at, starting_usdc)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                period['id'],
                period['name'],
                period['start'],
                period['end'],
                datetime.now().isoformat(),
                1000.0
            ))
            return cursor.lastrowid
    
    def get_last_processed_idx(self, session_id: int) -> int:
        """Get last processed candle index for resume."""
        with self._connection() as conn:
            row = conn.execute(
                'SELECT last_processed_idx FROM backtest_sessions WHERE id = ?',
                (session_id,)
            ).fetchone()
            return row['last_processed_idx'] if row else 0
    
    def update_progress(self, session_id: int, idx: int):
        """Update last processed index (for resume)."""
        with self._connection() as conn:
            conn.execute(
                'UPDATE backtest_sessions SET last_processed_idx = ? WHERE id = ?',
                (idx, session_id)
            )
    
    def log_decision(self, session_id: int, timestamp, symbol: str, 
                     action: str, requested_amount: float,
                     indicators: dict, portfolio: dict,
                     validation: dict,
                     fear_greed: int, market_regime: str,
                     api_stats: dict) -> int:
        """Log AI decision. Returns decision_id."""
        with self._connection() as conn:
            cursor = conn.execute('''
                INSERT INTO ai_decisions (
                    session_id, timestamp, symbol, action, requested_amount,
                    amount_valid, validation_note,
                    current_price, price_change_1h, price_change_24h,
                    ema_12, ema_26, rsi_14, bb_position, volume_ratio,
                    usdc_balance, asset_balance, asset_value_usdc, total_portfolio_value,
                    fear_greed_index, market_regime,
                    prompt_tokens, completion_tokens, api_latency_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id, timestamp, symbol, action, requested_amount,
                1 if validation['valid'] else 0, validation.get('note'),
                indicators['current_price'], indicators['price_change_1h'], 
                indicators['price_change_24h'],
                indicators['ema_12'], indicators['ema_26'], indicators['rsi_14'],
                indicators['bb_position'], indicators['volume_ratio'],
                portfolio['usdc_balance'], portfolio['asset_balance'],
                portfolio['asset_value'], portfolio['total_value'],
                fear_greed, market_regime,
                api_stats.get('prompt_tokens', 0), 
                api_stats.get('completion_tokens', 0),
                api_stats.get('latency_ms', 0)
            ))
            return cursor.lastrowid
    
    def update_decision_outcome(self, decision_id: int, price_5min: float, 
                                price_1h: float, direction: str, was_correct: bool):
        """Update decision with outcome data."""
        with self._connection() as conn:
            conn.execute('''
                UPDATE ai_decisions 
                SET price_5min_later = ?, price_1h_later = ?, 
                    price_direction = ?, was_correct = ?
                WHERE id = ?
            ''', (price_5min, price_1h, direction, 1 if was_correct else 0, decision_id))
    
    def log_trade(self, decision_id: int, session_id: int, timestamp,
                  trade: dict, portfolio_after: dict):
        """Log executed trade."""
        with self._connection() as conn:
            conn.execute('''
                INSERT INTO trades (
                    decision_id, session_id, timestamp, symbol, side,
                    quantity, price, value_usdc, fee_usdc,
                    usdc_after, asset_after
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                decision_id, session_id, timestamp, trade['symbol'], trade['side'],
                trade['quantity'], trade['price'], trade['value_usdc'], trade['fee_usdc'],
                portfolio_after['usdc'], portfolio_after['asset']
            ))
            
            # Update decision as executed
            conn.execute('''
                UPDATE ai_decisions 
                SET was_executed = 1, execution_price = ?, 
                    execution_quantity = ?, execution_fee = ?
                WHERE id = ?
            ''', (trade['price'], trade['quantity'], trade['fee_usdc'], decision_id))
    
    def mark_skipped(self, decision_id: int, reason: str):
        """Mark decision as skipped (not executed)."""
        with self._connection() as conn:
            conn.execute('''
                UPDATE ai_decisions 
                SET was_executed = 0, skipped_reason = ?
                WHERE id = ?
            ''', (reason, decision_id))
    
    def save_snapshot(self, session_id: int, timestamp, portfolio, 
                      prices: dict, fear_greed: int):
        """Save portfolio snapshot."""
        total_value = portfolio.get_total_value(prices)
        pnl = (total_value - 1000) / 1000 * 100
        
        with self._connection() as conn:
            conn.execute('''
                INSERT INTO portfolio_snapshots 
                (session_id, timestamp, usdc_balance, total_value, pnl_percent, 
                 fear_greed_index, holdings_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id, timestamp, portfolio.usdc, total_value, pnl,
                fear_greed, json.dumps(portfolio.holdings)
            ))
    
    def complete_session(self, session_id: int, final_stats: dict):
        """Mark session as completed with final stats."""
        with self._connection() as conn:
            conn.execute('''
                UPDATE backtest_sessions SET
                    completed_at = ?,
                    status = 'completed',
                    ending_usdc = ?,
                    ending_portfolio_value = ?,
                    total_return_percent = ?,
                    total_decisions = ?,
                    buy_count = ?,
                    sell_count = ?,
                    hold_count = ?,
                    executed_trades = ?,
                    win_rate = ?,
                    avg_fear_greed = ?,
                    market_return_percent = ?
                WHERE id = ?
            ''', (
                datetime.now().isoformat(),
                final_stats['ending_usdc'],
                final_stats['ending_value'],
                final_stats['total_return'],
                final_stats['total_decisions'],
                final_stats['buy_count'],
                final_stats['sell_count'],
                final_stats['hold_count'],
                final_stats['executed_trades'],
                final_stats['win_rate'],
                final_stats['avg_fear_greed'],
                final_stats['market_return'],
                session_id
            ))
    
    def get_decisions(self, session_id: int) -> list:
        """Get all decisions for a session."""
        with self._connection() as conn:
            rows = conn.execute(
                'SELECT * FROM ai_decisions WHERE session_id = ? ORDER BY id',
                (session_id,)
            ).fetchall()
            return [dict(row) for row in rows]
    
    def get_pending_outcomes(self, session_id: int) -> list:
        """Get decisions that need outcome updates."""
        with self._connection() as conn:
            rows = conn.execute('''
                SELECT id, timestamp, symbol, action, current_price 
                FROM ai_decisions 
                WHERE session_id = ? AND price_5min_later IS NULL
                ORDER BY id
            ''', (session_id,)).fetchall()
            return [dict(row) for row in rows]