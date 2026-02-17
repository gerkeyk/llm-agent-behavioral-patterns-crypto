from ai_providers.openai_provider import OpenAIProvider

# Initialize provider
# In the future, this can be switched based on config
# e.g., provider = AnthropicProvider() if config.AI_PROVIDER == 'anthropic'
_provider = OpenAIProvider()

def get_ai_decision(symbol: str, indicators: dict, portfolio: dict, 
                    can_buy: bool, can_sell: bool) -> dict:
    """
    Delegate decision making to the configured AI provider.
    """
    return _provider.get_decision(symbol, indicators, portfolio, can_buy, can_sell)

def create_prompt(symbol: str, indicators: dict, portfolio: dict, 
                  can_buy: bool, can_sell: bool) -> str:
    """
    Expose the prompt creation logic for debugging/logging purposes.
    Delegates to the provider's internal method if available, 
    otherwise returns a generic message.
    """
    if hasattr(_provider, '_create_prompt'):
        return _provider._create_prompt(symbol, indicators, portfolio, can_buy, can_sell)
    return "Prompt generation not exposed by current provider."
