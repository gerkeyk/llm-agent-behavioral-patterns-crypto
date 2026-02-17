from abc import ABC, abstractmethod

class BaseAIProvider(ABC):
    @abstractmethod
    def get_decision(self, symbol: str, indicators: dict, portfolio: dict, 
                     can_buy: bool, can_sell: bool) -> dict:
        """
        Get a trading decision from the AI provider.
        
        Args:
            symbol: The trading symbol (e.g., 'BTC/USDT')
            indicators: Dictionary of technical indicators
            portfolio: Dictionary of portfolio state
            can_buy: Boolean indicating if buying is allowed
            can_sell: Boolean indicating if selling is allowed
            
        Returns:
            dict: {
                'action': 'BUY'|'SELL'|'HOLD',
                'amount': float|None,
                'prompt_tokens': int,
                'completion_tokens': int,
                'latency_ms': int,
                'success': bool,
                'error': str (optional)
            }
        """
        pass
