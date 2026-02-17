# main.py

import sys
import signal
import logging
from dotenv import load_dotenv

# Load environment variables BEFORE importing other modules
load_dotenv()

from backtest_engine import BacktestEngine
from config import LOG_FILE

logger = logging.getLogger(__name__)

def signal_handler(signum, frame):
    """Handle graceful shutdown."""
    logger.info("Received shutdown signal, saving checkpoint...")
    sys.exit(0)

def main():
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("="*60)
    logger.info("AI TRADING BOT BACKTEST - STARTING")
    logger.info("="*60)
    logger.info(f"Logs saved to: {LOG_FILE}")
    
    engine = BacktestEngine()
    results = engine.run_all()
    
    logger.info("\nBacktest complete!")
    logger.info(f"Results saved to database. Run analyze_trading_data.py for behavioral analysis.")

if __name__ == "__main__":
    main()