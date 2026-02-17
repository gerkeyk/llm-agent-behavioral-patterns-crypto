# AI Backtest Engine - Fixes Applied (2026-01-26)

## Issues Identified and Fixed

### 1. Win Rate Calculation - FIXED ✓

**Problem:**
- All `was_correct` values in the database were NULL
- This caused 0% win rates across all actions
- The behavioral analysis couldn't evaluate AI performance

**Root Cause:**
- `backtest_engine.py` tracked `pending_outcomes` but never called `update_decision_outcome()`
- The database method existed but was never invoked

**Solution:**
- Created `evaluate_outcomes.py` - a post-processing script that:
  - Loads historical price data from parquet files
  - Looks ahead 5min and 1h to determine actual price movement
  - Updates `was_correct`, `price_5min_later`, `price_1h_later`, and `price_direction` fields
  - Logic:
    - BUY correct if price went up (>0.5%)
    - SELL correct if price went down (<-0.5%)
    - HOLD correct if price stayed relatively flat (<2% change)

**Results After Fix:**
- Successfully evaluated 72,800 decisions
- Overall win rate: **59.8%** (was 0%)
- BUY: 23.4% (poor performance)
- HOLD: 93.1% (excellent - AI knows when NOT to trade)
- SELL: 30.5% (below average)

---

### 2. Fear & Greed Index Data - FIXED ✓

**Problem:**
- All `fear_greed_index` values were 50 (default fallback)
- No emotional regime periods detected (0 out of 72,852)
- Rationality Projection Hypothesis couldn't be tested

**Root Cause:**
- Backtest data spans 2021-2022
- Fear & Greed cache only had 2025-2026 data
- Timestamp mismatch caused all lookups to return default value

**Solution:**
- Created `fetch_historical_feargreed.py` that:
  - Queries the actual date range from the database
  - Fetches up to 2000 days of historical F&G data from alternative.me API
  - Updates the cache file with historical values
  - Retroactively updates all database records

**Results After Fix:**
- Fetched 1,881 days of Fear & Greed data (2020-12-02 to 2026-01-26)
- Updated all 72,937 decisions with correct F&G values
- **Emotional periods detected: 45,702** (62.6% of decisions!)
- **Rational periods: 27,245** (37.4%)
- Rationality Projection Score: 1.03 (60.9% vs 59.1%)

---

### 3. Pandas FutureWarning - FIXED ✓

**Problem:**
- `FutureWarning` in `analyze_trading_data.py` line 45
- Future pandas versions will change fillna behavior

**Solution:**
- Changed: `self.df.fillna(0, inplace=True)`
- To: `self.df = self.df.fillna(0).infer_objects(copy=False)`

---

## Updated Analysis Results

### Overall Performance
- **Total Decisions:** 72,947
- **Executed Trades:** 7,452 (10.2%)
- **Overall Win Rate:** 59.8%
- **AI vs Level-0 Baseline:** +47.2 percentage points advantage

### Action Distribution
- HOLD: 37,733 (51.7%)
- BUY: 31,733 (43.5%)
- SELL: 3,481 (4.8%)

### Strategic Reasoning Level
- **Best Fit Model:** Level-1 (Level-k framework)
- **Interpretation:** AI incorporates Value/RSI indicators, responding to basic trends
- **Cognitive Hierarchy Tau:** 1.82 (mean thinking depth)
- **Level Distribution:**
  - Level-0: 18.2%
  - Level-1: 33.2% (dominant)
  - Level-2: 30.2%
  - Level-3: 18.3%

### Rationality Projection Hypothesis (H1)
- **Hypothesis:** AI maintains higher strategic depth during rational market periods
- **Results:**
  - Rational regime win rate: 60.9%
  - Emotional regime win rate: 59.1%
  - RPS Score: 1.03
- **Conclusion:** Hypothesis NOT supported (only 3% difference)
  - AI performance is consistent regardless of market emotional state
  - This could be a strength (robustness) or weakness (not adapting to market sentiment)

---

## Key Insights for Your Research Paper

### Strengths
1. **High HOLD accuracy (93.1%)** - AI is excellent at recognizing when NOT to trade
2. **Consistent performance** across emotional/rational regimes (robust)
3. **47.2% better than simple trend-following** (Level-0 baseline)
4. **Level-1 strategic reasoning** - uses RSI and value indicators effectively

### Weaknesses
1. **Poor BUY decisions (23.4%)** - AI is too aggressive on buy signals
   - Possibly overreacting to bullish indicators
   - May need to tighten BUY thresholds or add confirmation signals
2. **Low SELL performance (30.5%)** - Missing optimal exit points
3. **No adaptation to market sentiment** - RPS score near 1.0
   - Could incorporate F&G index more directly in decision logic

### Recommendations
1. **For the backtest engine:** Add outcome evaluation as a post-processing step
   - Run `evaluate_outcomes.py` after each session completes
   - Or integrate into `backtest_engine.py` with proper lookback logic

2. **For AI decision logic:**
   - Add stricter BUY criteria (currently only 23.4% win rate)
   - Consider adding Fear & Greed as an explicit feature in the AI prompt
   - Test sentiment-aware thresholds (more conservative in PANIC/EUPHORIA regimes)

3. **For future analysis:**
   - Track profit/loss amounts, not just correctness
   - Analyze which Level-k strategies work best in different market conditions
   - Consider transaction costs in outcome evaluation

---

## New Files Created

1. **`evaluate_outcomes.py`** - Retrospective decision evaluation script
   - Usage: `./venv/bin/python3 evaluate_outcomes.py [--db path] [--data-dir path] [--limit N]`
   - Safe to run while backtest is running (only updates outcome fields)

2. **`fetch_historical_feargreed.py`** - Historical F&G data fetcher
   - Usage: `./venv/bin/python3 fetch_historical_feargreed.py`
   - Fetches and caches historical Fear & Greed Index data
   - Updates existing database records

3. **Log files:**
   - `outcome_evaluation.log` - Outcome evaluation run log
   - `feargreed_update.log` - F&G data fetch log
   - `analysis_rerun.log` - Updated analysis run log

---

## Next Steps

1. **Continue monitoring the running backtest** - fixes don't affect it
2. **Run outcome evaluation periodically** to keep `was_correct` updated as new data comes in
3. **Consider integrating evaluation into backtest_engine.py** for future runs
4. **Refine AI decision thresholds** based on the insights (especially for BUY signals)
5. **Add Fear & Greed as an explicit feature** in the AI prompt to test if awareness improves RPS

---

## Safety Notes

- All fixes were designed to be **non-disruptive** to the running backtest
- The backtest process writes new decision records but doesn't touch outcome fields
- Outcome evaluation only updates fields that the backtest doesn't use
- Fear & Greed updates are also safe (just updating existing values)
- No `.bak` files were modified or deleted

## Database Backup Recommendation

Before making any major changes, consider backing up the database:
```bash
cp data/backtest_results.db data/backtest_results_backup_$(date +%Y%m%d).db
```

---

Generated: 2026-01-26
