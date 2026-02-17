# checkpoint.py

import json
import os
from datetime import datetime
from config import CHECKPOINT_DIR

class Checkpoint:
    """Save and restore backtest state for resumption."""
    
    @staticmethod
    def save(session_id: int, period_id: int, candle_idx: int, 
             portfolio_data: dict, stats: dict):
        """Save checkpoint after each candle."""
        filepath = os.path.join(CHECKPOINT_DIR, f"session_{session_id}.json")
        
        data = {
            'session_id': session_id,
            'period_id': period_id,
            'candle_idx': candle_idx,
            'portfolio': portfolio_data,
            'stats': stats,
            'saved_at': datetime.now().isoformat()
        }
        
        # Write atomically (write to temp, then rename)
        temp_path = filepath + '.tmp'
        with open(temp_path, 'w') as f:
            json.dump(data, f)
        os.replace(temp_path, filepath)
    
    @staticmethod
    def load(session_id: int) -> dict:
        """Load checkpoint if exists."""
        filepath = os.path.join(CHECKPOINT_DIR, f"session_{session_id}.json")
        
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return json.load(f)
        return None
    
    @staticmethod
    def delete(session_id: int):
        """Delete checkpoint after successful completion."""
        filepath = os.path.join(CHECKPOINT_DIR, f"session_{session_id}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
