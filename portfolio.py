# portfolio.py

from dataclasses import dataclass, field
from typing import Dict, Optional
import json
from config import TRADING_SYMBOLS, STARTING_USDC, MIN_TRADE_USDC, FEE_RATE

@dataclass
class Portfolio:
    """Virtual portfolio with validation."""
    usdc: float = STARTING_USDC
    holdings: Dict[str, float] = field(default_factory=dict)
    
    def __post_init__(self):
        # Initialize all holdings to 0
        for symbol in TRADING_SYMBOLS:
            asset = symbol.replace("USDC", "")
            if asset not in self.holdings:
                self.holdings[asset] = 0.0
    
    @classmethod
    def new(cls) -> 'Portfolio':
        """Create fresh portfolio."""
        return cls(usdc=STARTING_USDC, holdings={})
    
    @classmethod
    def from_checkpoint(cls, data: dict) -> 'Portfolio':
        """Restore from checkpoint."""
        p = cls(usdc=data['usdc'], holdings=data['holdings'])
        return p
    
    def to_checkpoint(self) -> dict:
        """Export for checkpoint."""
        return {'usdc': self.usdc, 'holdings': self.holdings.copy()}
    
    def get_total_value(self, prices: Dict[str, float]) -> float:
        """Calculate total portfolio value in USDC."""
        total = self.usdc
        for symbol in TRADING_SYMBOLS:
            asset = symbol.replace("USDC", "")
            if asset in self.holdings and self.holdings[asset] > 0:
                if symbol in prices:
                    total += self.holdings[asset] * prices[symbol]
        return total
    
    def get_asset_balance(self, symbol: str) -> float:
        """Get balance for a specific asset."""
        asset = symbol.replace("USDC", "")
        return self.holdings.get(asset, 0.0)
    
    def get_asset_value(self, symbol: str, price: float) -> float:
        """Get value of asset holdings in USDC."""
        return self.get_asset_balance(symbol) * price
    
    def validate_buy(self, amount: float) -> dict:
        """
        Validate BUY order BEFORE AI call.
        Returns: {'valid': bool, 'amount': adjusted_amount, 'note': str}
        """
        if self.usdc < MIN_TRADE_USDC:
            return {
                'valid': False, 
                'amount': 0, 
                'note': f'Insufficient USDC: {self.usdc:.2f} < {MIN_TRADE_USDC}'
            }
        
        if amount is None or amount <= 0:
            return {'valid': False, 'amount': 0, 'note': 'Invalid amount'}
        
        # Cap at available balance
        actual_amount = min(amount, self.usdc)
        
        if actual_amount < MIN_TRADE_USDC:
            return {
                'valid': False,
                'amount': 0,
                'note': f'Amount too small after cap: {actual_amount:.2f}'
            }
        
        return {
            'valid': True,
            'amount': actual_amount,
            'note': 'OK' if actual_amount == amount else f'Capped from {amount:.2f}'
        }
    
    def validate_sell(self, symbol: str, quantity: float) -> dict:
        """
        Validate SELL order BEFORE AI call.
        Returns: {'valid': bool, 'amount': adjusted_amount, 'note': str}
        """
        asset = symbol.replace("USDC", "")
        available = self.holdings.get(asset, 0)
        
        if available <= 0:
            return {
                'valid': False,
                'amount': 0,
                'note': f'No {asset} holdings to sell'
            }
        
        if quantity is None or quantity <= 0:
            return {'valid': False, 'amount': 0, 'note': 'Invalid quantity'}
        
        # Cap at available holdings
        actual_qty = min(quantity, available)
        
        return {
            'valid': True,
            'amount': actual_qty,
            'note': 'OK' if actual_qty == quantity else f'Capped from {quantity:.6f}'
        }
    
    def can_trade(self, symbol: str) -> dict:
        """
        Check if ANY trade is possible for this symbol.
        Call BEFORE asking AI to avoid wasted API calls.
        """
        asset = symbol.replace("USDC", "")
        can_buy = self.usdc >= MIN_TRADE_USDC
        can_sell = self.holdings.get(asset, 0) > 0
        
        return {
            'can_buy': can_buy,
            'can_sell': can_sell,
            'can_trade': can_buy or can_sell,
            'usdc_available': self.usdc,
            'asset_available': self.holdings.get(asset, 0)
        }
    
    def execute_buy(self, symbol: str, usdc_amount: float, price: float) -> Optional[dict]:
        """
        Execute BUY. Returns trade details or None.
        MUST call validate_buy() first!
        """
        asset = symbol.replace("USDC", "")
        
        # Final safety check
        if usdc_amount > self.usdc:
            usdc_amount = self.usdc
        
        if usdc_amount < MIN_TRADE_USDC:
            return None
        
        fee = usdc_amount * FEE_RATE
        quantity = (usdc_amount - fee) / price
        
        # Update balances
        self.usdc -= usdc_amount
        self.holdings[asset] = self.holdings.get(asset, 0) + quantity
        
        return {
            'side': 'BUY',
            'symbol': symbol,
            'quantity': quantity,
            'price': price,
            'value_usdc': usdc_amount,
            'fee_usdc': fee
        }
    
    def execute_sell(self, symbol: str, quantity: float, price: float) -> Optional[dict]:
        """
        Execute SELL. Returns trade details or None.
        MUST call validate_sell() first!
        """
        asset = symbol.replace("USDC", "")
        
        # Final safety check
        available = self.holdings.get(asset, 0)
        if quantity > available:
            quantity = available
        
        if quantity <= 0:
            return None
        
        gross = quantity * price
        fee = gross * FEE_RATE
        net = gross - fee
        
        # Update balances
        self.holdings[asset] -= quantity
        self.usdc += net
        
        return {
            'side': 'SELL',
            'symbol': symbol,
            'quantity': quantity,
            'price': price,
            'value_usdc': gross,
            'fee_usdc': fee
        }
    
    def get_state_for_ai(self, symbol: str, price: float, all_prices: dict) -> dict:
        """Get portfolio state formatted for AI prompt."""
        asset = symbol.replace("USDC", "")
        asset_balance = self.holdings.get(asset, 0)
        
        return {
            'usdc_balance': self.usdc,
            'asset_balance': asset_balance,
            'asset_value': asset_balance * price,
            'total_value': self.get_total_value(all_prices)
        }