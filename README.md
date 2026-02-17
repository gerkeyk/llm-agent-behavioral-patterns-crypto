# Investigating Large Language Model Agent Behavioral Patterns in Cryptocurrency Markets

**Research Thesis:** *Suure keelemudeli agendi käitumismustrite uurimine krüptoturgudel*

This repository contains the implementation code and behavioral analysis framework for a high school research thesis examining how GPT-4o-mini trading agents exhibit behavioral patterns consistent with bounded rationality models from game theory when making cryptocurrency trading decisions.

## Abstract

This research investigates whether large language models (LLMs) acting as autonomous trading agents exhibit systematic behavioral patterns predicted by game-theoretic models of bounded rationality. Using GPT-4o-mini, we simulate cryptocurrency trading across 10 distinct historical market periods (2021-2024) and analyze decision patterns through three frameworks: Level-k reasoning, Cognitive Hierarchy Theory (CHT), and Inequity Aversion. The agent receives market data and portfolio state, outputting trading actions without explanatory reasoning, allowing pure behavioral analysis of choices versus outcomes.

## Research Context

**Behavioral Game Theory Models:**
- **Level-k Model** (Stahl & Wilson, 1994, 1995): Hierarchical reasoning where Level-0 players follow simple heuristics and Level-k players best-respond to Level-(k-1)
- **Cognitive Hierarchy Theory** (Camerer, Ho & Chong, 2004): Players assume others follow a Poisson distribution of reasoning depths
- **Inequity Aversion** (Fehr & Schmidt, 1999): Agents value both absolute and relative payoffs, exhibiting loss aversion

**Application to LLM Trading:**
We treat the LLM agent's trading decisions as revealed preferences, applying Maximum Likelihood Estimation (MLE) to fit behavioral parameters and using Akaike Information Criterion (AIC) for model comparison.

## Key Results Summary

### Level-k Analysis
- **Best Fit:** Level-1 player (reasoning one step ahead of naive trend-following)
- **λ (logit precision):** 1.279
- **AIC:** 178021.11
- **Interpretation:** GPT-4o-mini exhibits moderately sophisticated reasoning, best-responding to simple momentum strategies rather than following them directly

### Cognitive Hierarchy Theory
- **τ (tau parameter):** 1.82
- **Interpretation:** Agent assumes others use reasoning depths centered around 1-2 levels
- **Rationality Projection Score (RPS):** 1.03
- **Interpretation:** Win rate remains consistent across emotional vs. rational market conditions (F&G Index)

### Inequity Aversion
- **χ² test statistic:** 315.23
- **p-value:** < 0.000001 (highly significant)
- **Interpretation:** Strong evidence that position sizing correlates with portfolio imbalances, suggesting aversion to extreme allocations

## Repository Structure

```
ai_backtest/
├── trading_bot/              # Core trading simulation
│   ├── main.py               # Entry point for backtest
│   ├── backtest_engine.py    # Main orchestration engine
│   ├── portfolio.py          # Portfolio management & position tracking
│   ├── database.py           # SQLite operations for decision logging
│   ├── data_fetcher.py       # Binance historical data retrieval
│   ├── indicators.py         # Technical indicators (RSI, MACD, etc.)
│   ├── fear_greed.py         # Fear & Greed Index integration
│   └── ai_providers/         # AI provider abstraction layer
│       ├── base.py
│       └── openai_provider.py
│
├── analysis/                 # Behavioral analysis scripts
│   ├── analyze_trading_data.py   # Level-k & CHT MLE fitting
│   ├── qre_analysis.py           # Quantal Response Equilibrium
│   └── evaluate_outcomes.py      # Outcome evaluation metrics
│
├── data/                     # Data directory (gitignored)
│   ├── historical/           # Cached price data & Fear/Greed Index
│   ├── exports/              # CSV exports of decisions/trades
│   ├── checkpoints/          # Session checkpoints
│   └── backtest_results.db   # SQLite database with all decisions
│
├── config.py                 # Configuration constants
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variable template
├── .gitignore
└── README.md
```

## Installation

### Prerequisites
- Python 3.8+
- OpenAI API key (for GPT-4o-mini access)
- Binance API access (optional - historical data is cached)

### Setup

1. **Clone the repository:**
```bash
git clone https://github.com/yourusername/llm-agent-behavioral-patterns-crypto.git
cd llm-agent-behavioral-patterns-crypto/ai_backtest
```

2. **Create virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables:**
```bash
cp .env.example .env
# Edit .env and add your OpenAI API key
```

## Configuration

### Environment Variables (.env.example)

```bash
# Required: OpenAI API Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Optional: Binance API (historical data pre-cached)
BINANCE_API_KEY=your_binance_api_key_here
BINANCE_SECRET=your_binance_secret_here

# Trading Configuration
INITIAL_CAPITAL=1000                          # Starting USDC per period
TRADING_PAIRS=BTCUSDC,ETHUSDC,SOLUSDC,XRPUSDC,DOGEUSDC
INTERVAL=5m                                   # Candle interval

# GPT Model Settings
GPT_MODEL=gpt-4o-mini
GPT_TEMPERATURE=0.4                           # Lower = more deterministic
```

### Test Periods

The backtest runs across 10 carefully selected 2-week periods representing different market regimes:

1. **Jan 2021** - Early Bull Market
2. **Jun 2021** - Post-Crash Recovery
3. **Nov 2021** - All-Time High Peak
4. **Apr 2022** - Declining Market
5. **Aug 2022** - Deep Bear Market
6. **Jan 2023** - Bear Market Bottom
7. **Jun 2023** - Recovery Phase
8. **Oct 2023** - Sideways Consolidation
9. **Mar 2024** - ETF Rally
10. **Aug 2024** - Consolidation Phase

## Usage

### Running the Trading Backtest

```bash
# Option 1: Using helper script
./run.sh

# Option 2: Direct execution
source venv/bin/activate
python main.py
```

**Output:**
- SQLite database: `data/backtest_results.db`
- Exports: `data/exports/*.csv`
- Logs: `data/backtest.log`

### Running Behavioral Analysis

After completing the backtest, analyze the decision patterns:

```bash
# Level-k and Cognitive Hierarchy Analysis
python analyze_trading_data.py --db data/backtest_results.db

# Quantal Response Equilibrium Analysis
python qre_analysis.py --db data/backtest_results.db

# Outcome Evaluation
python evaluate_outcomes.py --db data/backtest_results.db
```

**Analysis Outputs:**
- `analysis_results.json` - Level-k parameters, AIC scores
- `analysis_report.txt` - Human-readable summary
- `analysis_qre_results.json` - QRE parameters
- Console output with statistical tests

## Data Schema

### Database Tables

**`backtest_sessions`**
- Session metadata (period, dates, returns, Sharpe ratio, win rate)

**`ai_decisions`**
- AI output: action (BUY/SELL/HOLD), amount
- Market context: price, RSI, MACD, volume
- Portfolio state: balances, total value
- Outcomes: price change 5min/1h later, was_correct boolean
- External context: Fear & Greed Index, market regime

**`trades`**
- Execution details: quantity, price, fees, slippage

**`portfolio_snapshots`**
- Hourly portfolio value tracking for returns calculation

## Methodology

### Trading Agent Design

The GPT-4o-mini agent receives:
- **Market Data:** Current price, RSI, MACD, Bollinger Bands, volume
- **Portfolio State:** USDC balance, crypto holdings, total value
- **Constraints:** Boolean flags for can_buy, can_sell

The agent responds with **action-only JSON:**
```json
{
  "action": "BUY" | "SELL" | "HOLD",
  "amount": <number or null>
}
```

**Critical Design Choice:** No reasoning text is requested or logged. This allows analysis of revealed preferences through actions, not post-hoc rationalizations.

### Behavioral Analysis Pipeline

1. **Data Collection:** 10 periods × 5 assets × ~4,000 candles = ~200,000 decisions
2. **Feature Engineering:** Technical indicators, portfolio metrics, market regime classification
3. **Model Fitting:**
   - Level-k: MLE over {k=0,1,2,3}, optimize λ parameter
   - CHT: Fit τ (tau) parameter via grid search
   - Inequity Aversion: χ² test on position sizing vs. portfolio imbalance
4. **Model Selection:** AIC-based comparison across Level-k depths
5. **Statistical Testing:** Bootstrap confidence intervals, χ² tests

## Results Interpretation

### Level-1 Behavior
The agent exhibits **Level-1 reasoning**, meaning it:
- Recognizes naive trend-following (Level-0) is exploitable
- Best-responds by anticipating reversions
- Does not model higher-order strategic thinking (Level-2+)

**Implication:** GPT-4o-mini demonstrates bounded rationality—more sophisticated than reflexive momentum trading, but not fully recursive modeling.

### Cognitive Hierarchy (τ = 1.82)
The fitted τ parameter suggests the agent assumes:
- ~15% of "other traders" are Level-0
- ~28% are Level-1
- ~25% are Level-2
- Remaining distribution across higher levels

**Implication:** The model's internal representation approximates a diverse market with heterogeneous reasoning depths.

### Rationality Projection Score (RPS = 1.03)
Win rate is nearly identical in emotional (F&G < 30 or > 70) vs. rational (F&G 30-70) market conditions.

**Interpretation:** The agent does not exhibit "emotional" decision biases based on sentiment indicators, maintaining consistent performance.

### Inequity Aversion (χ² = 315.23, p < 0.000001)
Position sizes correlate strongly with portfolio imbalances, showing:
- Smaller trades when portfolio is heavily skewed
- Larger trades when portfolio is balanced
- Analogous to loss aversion / risk management

**Implication:** LLM agents may exhibit risk-averse rebalancing behavior similar to human inequity aversion.

## Cost Estimates

- **OpenAI API:** ~$5-10 per full backtest run (10 periods, ~200k decisions)
- **Binance API:** Free (public historical data)
- **Fear & Greed API:** Free

## Limitations

1. **Simulated Environment:** No real capital at risk; execution assumptions may not reflect live trading
2. **Historical Bias:** 10 periods may not capture full market diversity
3. **Model Assumptions:** Level-k and CHT assume discrete reasoning levels; reality may be continuous
4. **Single LLM:** Results specific to GPT-4o-mini; other models may differ
5. **No Multi-Agent Dynamics:** Agent trades in isolation, not against other LLM agents

## Future Research Directions

- **Multi-Agent Simulation:** Pit multiple LLM agents against each other
- **Prompt Engineering:** Test different system prompts for varying risk profiles
- **Model Comparison:** GPT-4, Claude, Gemini behavioral differences
- **Reinforcement Learning Hybrid:** Combine LLM reasoning with RL fine-tuning
- **Real-Time Deployment:** Validate findings in live paper trading

## Citation

If you use this code or findings in your research, please cite:

```bibtex
@mastersthesis{yourname2025llm,
  title={Investigating Large Language Model Agent Behavioral Patterns in Cryptocurrency Markets},
  author={Your Name},
  year={2025},
  school={Your High School},
  type={Research Thesis},
  note={Code: https://github.com/yourusername/llm-agent-behavioral-patterns-crypto}
}
```

## License

This code is released for **research and educational purposes only**.

**Important Disclaimers:**
- This is **not financial advice**
- Do not use this code for live trading without extensive additional validation
- Cryptocurrency trading involves significant risk of loss
- Past simulated performance does not guarantee future results

MIT License - See LICENSE file for details.

## Acknowledgments

- **Behavioral Game Theory:** Stahl & Wilson (1994), Camerer et al. (2004), Fehr & Schmidt (1999)
- **Data Sources:** Binance API, Alternative.me Fear & Greed Index
- **AI Provider:** OpenAI GPT-4o-mini
- **Thesis Advisor:** [Your Advisor Name]

## Contact

For questions about this research:
- **GitHub Issues:** [Project Issues Page](https://github.com/yourusername/llm-agent-behavioral-patterns-crypto/issues)
- **Email:** your.email@example.com

---

**Research Period:** 2024-2025
**Institution:** Your High School Name
**Thesis Language:** Estonian
**Code Documentation:** English
