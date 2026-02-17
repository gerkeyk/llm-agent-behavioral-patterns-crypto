#!/usr/bin/env python3
"""
Trading Data Analysis Tool for Behavioral Game Theory Research.
Calculates Level-k metrics, Cognitive Hierarchy parameters, and Rationality Projection scores
from AI trading bot decisions.

References:
- Level-0 trend-following: De Long, Shleifer, Summers & Waldmann (1990)
- Level-k model: Stahl & Wilson (1994, 1995)
- Logit choice: McKelvey & Palfrey (1995)
- Cognitive Hierarchy: Camerer, Ho & Chong (2004)
- AIC: Akaike (1974)
"""

import sqlite3
import pandas as pd
import numpy as np
import argparse
import json
import sys
from scipy.optimize import minimize, minimize_scalar
from scipy.stats import poisson

class BehavioralAnalyzer:
    def __init__(self, db_path):
        self.db_path = db_path
        self.df = None
        self.results = {}
        
    def load_data(self):
        """Load and preprocess data from SQLite."""
        print(f"Loading data from {self.db_path}...")
        try:
            conn = sqlite3.connect(self.db_path)
            query = "SELECT * FROM ai_decisions"
            self.df = pd.read_sql_query(query, conn)
            conn.close()
            
            # Preprocessing
            # Map actions to numeric: BUY=1, SELL=-1, HOLD=0
            action_map = {'BUY': 1, 'SELL': -1, 'HOLD': 0}
            self.df['action_num'] = self.df['action'].map(action_map).fillna(0)
            
            # Handle missing values
            self.df = self.df.fillna(0).infer_objects(copy=False)
            
            print(f"Loaded {len(self.df)} records.")
            return True
        except Exception as e:
            print(f"Error loading data: {e}")
            return False

    def _logit_prob(self, utilities, lambda_param):
        """
        Calculate Logit probabilities for actions [-1, 0, 1].
        P(a) = exp(lambda * U(a)) / sum(exp(lambda * U(a')))
        """
        # utilities shape: (N, 3) for actions [-1, 0, 1]
        # lambda_param: scalar
        
        # Avoid overflow by subtracting max
        scaled_u = utilities * lambda_param
        max_u = np.max(scaled_u, axis=1, keepdims=True)
        exp_u = np.exp(scaled_u - max_u)
        sum_exp_u = np.sum(exp_u, axis=1, keepdims=True)
        probs = exp_u / sum_exp_u
        return probs

    def _calculate_utilities(self, k, df_subset=None):
        """
        Define Expected Utility (EU) for each level k.
        Returns array of shape (N, 3) corresponding to actions [SELL (-1), HOLD (0), BUY (1)].
        
        Level Definitions (Heuristic approximations for Research Paper):
        - L0 (Trend): Utility proportional to 1H Price Change.
        - L1 (Value): L0 + RSI Mean Reversion (Buy if low RSI).
        - L2 (Vol): L1 + Bollinger Band Reversion.
        - L3 (Conf): L2 + Volume Confirmation.
        """
        data = df_subset if df_subset is not None else self.df
        n = len(data)
        utils = np.zeros((n, 3)) # cols: SELL, HOLD, BUY
        
        # Feature extraction
        # Normalize features roughly to [-1, 1] range for stability
        r = data['price_change_1h'].values / 100.0  # Trend
        rsi_sig = (50 - data['rsi_14'].values) / 50.0  # +1 if RSI=0 (Buy), -1 if RSI=100 (Sell)
        bb_sig = (0.5 - data['bb_position'].values) * 2.0 # +1 if Low Band, -1 if High Band
        
        # Action multipliers: SELL=-1, HOLD=0, BUY=1
        # We construct utility for 'acting' (Buy/Sell). Hold usually has 0 utility relative to active moves in these simple models,
        # or we can model Hold as having a fixed utility threshold. 
        # Here we assume U(Hold) = 0, and U(Buy/Sell) depends on signal strength.
        
        # Common Signal Construction
        signal = np.zeros(n)
        
        if k == 0:
            # Level-0: Trend Follower
            # If r > 0, Buy is good. U(Buy) > 0.
            signal = r 
        elif k == 1:
            # Level-1: Trend + RSI (Strategic/Value)
            # Weights can be arbitrary or equal. Using equal for "Sophistication" proxy.
            signal = r + rsi_sig
        elif k == 2:
            # Level-2: L1 + BB (Volatility Aware)
            signal = r + rsi_sig + bb_sig
        elif k == 3:
            # Level-3: L2 + Volume weighted
            vol_ratio = np.clip(data['volume_ratio'].values, 0, 5) / 5.0
            signal = (r + rsi_sig + bb_sig) * (1 + vol_ratio)
            
        # Assign Utilities
        # U(Sell) = -signal (if signal is positive/bullish, selling is bad)
        # U(Hold) = 0 (Reference)
        # U(Buy) = signal
        
        utils[:, 0] = -signal # SELL column (index 0 corresponds to action -1?)
        # Wait, let's map indices carefully.
        # Actions: -1 (Sell), 0 (Hold), 1 (Buy)
        # Indices: 0, 1, 2
        
        utils[:, 0] = -signal  # Action -1
        utils[:, 1] = 0.0      # Action 0
        utils[:, 2] = signal   # Action 1
        
        return utils

    def _neg_log_likelihood(self, lambda_param, k, df_subset=None):
        """Calculate Negative Log Likelihood for a specific level k and lambda."""
        if lambda_param < 0: return 1e9 # Enforce positive lambda
        
        data = df_subset if df_subset is not None else self.df
        utils = self._calculate_utilities(k, data)
        probs = self._logit_prob(utils, lambda_param)
        
        # Get probabilities of actually chosen actions
        # Action map: -1 -> 0, 0 -> 1, 1 -> 2
        action_indices = (data['action_num'].values + 1).astype(int)
        
        chosen_probs = probs[np.arange(len(data)), action_indices]
        
        # Avoid log(0)
        chosen_probs = np.clip(chosen_probs, 1e-9, 1.0)
        nll = -np.sum(np.log(chosen_probs))
        return nll

    def run_level_k_analysis(self):
        """Fit Level-k models 0-3 and select best."""
        print("Running Level-k Estimation...")
        results = {}
        best_aic = float('inf')
        best_level = -1
        
        for k in range(4):
            # Optimization for lambda
            res = minimize_scalar(
                self._neg_log_likelihood, 
                args=(k,), 
                bounds=(0.1, 20.0), 
                method='bounded'
            )
            
            lam = res.x
            nll = res.fun
            # AIC = 2*k - 2*ln(L) -> k=1 parameter (lambda) per model
            aic = 2*1 + 2*nll 
            
            results[f"level_{k}"] = {
                "lambda": round(lam, 4),
                "log_likelihood": round(-nll, 2),
                "aic": round(aic, 2)
            }
            
            if aic < best_aic:
                best_aic = aic
                best_level = k
                
        results["best_level"] = best_level
        
        # Interpretation
        interpretations = {
            0: "AI behaves like a simple Trend Follower (Level-0)",
            1: "AI incorporates Value/RSI, responding to basic trends (Level-1)",
            2: "AI accounts for Volatility and Value (Level-2)",
            3: "AI uses complex confirmation signals (Level-3)"
        }
        results["interpretation"] = interpretations.get(best_level, "Unknown")
        
        self.results["level_k_analysis"] = results
        return results

    def run_cht_analysis(self):
        """Estimate Cognitive Hierarchy Tau."""
        print("Running CHT Analysis...")
        
        # Pre-calculate probabilities for all levels at their optimal lambdas
        # to save compute during mixture optimization?
        # Ideally, we optimize tau, and for each level, we assume a fixed lambda 
        # (often taken as the average or individual optimal).
        # We will use the individual optimal lambdas found in Level-k step.
        
        if "level_k_analysis" not in self.results:
            self.run_level_k_analysis()
            
        lambdas = [self.results["level_k_analysis"][f"level_{k}"]["lambda"] for k in range(4)]
        
        # Precompute prob matrices for each level: Shape (N, 3)
        level_probs = []
        for k in range(4):
            utils = self._calculate_utilities(k)
            probs = self._logit_prob(utils, lambdas[k])
            level_probs.append(probs) # List of (N, 3) arrays
            
        action_indices = (self.df['action_num'].values + 1).astype(int)
        
        def cht_neg_log_like(tau):
            if tau <= 0.01 or tau > 10: return 1e9
            
            # Poisson weights
            weights = poisson.pmf(np.arange(4), tau)
            # Normalize to sum to 1 for just these 4 levels (truncated Poisson)
            weights /= np.sum(weights)
            
            # Mixture probability for chosen actions
            # P(a) = sum_k f(k) * P_k(a)
            mix_probs = np.zeros(len(self.df))
            for k in range(4):
                # Prob of chosen action under level k
                p_choice_k = level_probs[k][np.arange(len(self.df)), action_indices]
                mix_probs += weights[k] * p_choice_k
                
            mix_probs = np.clip(mix_probs, 1e-9, 1.0)
            return -np.sum(np.log(mix_probs))

        res = minimize_scalar(cht_neg_log_like, bounds=(0.01, 5.0), method='bounded')
        
        optimal_tau = res.x
        nll = res.fun
        aic = 2*1 + 2*nll
        
        # Level distribution
        raw_dist = poisson.pmf(np.arange(4), optimal_tau)
        dist = raw_dist / np.sum(raw_dist)
        dist_dict = {str(k): round(float(p), 3) for k, p in enumerate(dist)}
        
        self.results["cht_analysis"] = {
            "optimal_tau": round(optimal_tau, 3),
            "level_distribution": dist_dict,
            "mean_level": round(optimal_tau, 3), # Theoretical mean is tau
            "log_likelihood": round(-nll, 2),
            "aic": round(aic, 2)
        }
        return self.results["cht_analysis"]

    def compare_models(self):
        """Compare Best Level-k vs CHT."""
        lk_best = self.results["level_k_analysis"]["level_" + str(self.results["level_k_analysis"]["best_level"])]
        cht = self.results["cht_analysis"]
        
        lk_aic = lk_best["aic"]
        cht_aic = cht["aic"]
        
        delta = abs(lk_aic - cht_aic)
        best = "Level-k" if lk_aic < cht_aic else "CHT"
        
        # Evidence strength (Burnham & Anderson 2002)
        if delta < 2: strength = "Weak"
        elif delta < 6: strength = "Positive"
        elif delta < 10: strength = "Strong"
        else: strength = "Very Strong"
        
        self.results["model_comparison"] = {
            "best_model": best,
            "delta_aic": round(delta, 2),
            "evidence_strength": strength
        }

    def analyze_rationality_projection(self):
        """Test H1: Rationality Projection in Emotional vs Rational regimes."""
        print("Analyzing Rationality Projection...")
        
        # Split data
        emotional_mask = (self.df['fear_greed_index'] < 30) | (self.df['fear_greed_index'] > 70)
        rational_mask = ~emotional_mask
        
        df_em = self.df[emotional_mask]
        df_ra = self.df[rational_mask]
        
        def analyze_subset(sub_df):
            if len(sub_df) == 0: return {"n": 0, "win_rate": 0, "best_level": -1}
            
            # Win rate
            win_rate = sub_df['was_correct'].mean()
            
            # Best Level fit
            best_aic = float('inf')
            best_k = 0
            for k in range(3): # Check L0-L2 only for speed
                # optimize lambda
                res = minimize_scalar(
                    self._neg_log_likelihood, 
                    args=(k, sub_df), 
                    bounds=(0.1, 10.0), 
                    method='bounded'
                )
                aic = 2 + 2*res.fun
                if aic < best_aic:
                    best_aic = aic
                    best_k = k
            
            return {
                "n": int(len(sub_df)),
                "win_rate": round(float(win_rate), 3),
                "best_level": int(best_k)
            }
            
        res_em = analyze_subset(df_em)
        res_ra = analyze_subset(df_ra)
        
        rps = 0.0
        if res_em['win_rate'] > 0:
            rps = res_ra['win_rate'] / res_em['win_rate']
            
        supported = "No"
        if rps > 1.3: supported = "Strong"
        elif rps > 1.1: supported = "Moderate"
        
        self.results["rationality_projection"] = {
            "emotional_periods": res_em,
            "rational_periods": res_ra,
            "rps_score": round(rps, 2),
            "hypothesis_supported": supported
        }

    def basic_stats(self):
        """Calculate basic descriptive stats."""
        stats = {}
        stats["total_decisions"] = int(len(self.df))
        stats["executed_trades"] = int(self.df['was_executed'].sum())
        
        # Action dist
        vc = self.df['action'].value_counts().to_dict()
        stats["action_distribution"] = vc
        
        # Win rates
        stats["overall_win_rate"] = round(self.df['was_correct'].mean(), 3)
        
        wr_by_action = self.df.groupby('action')['was_correct'].mean().to_dict()
        stats["win_rate_by_action"] = {k: round(v, 3) for k, v in wr_by_action.items()}
        
        self.results["basic_stats"] = stats

    def level0_baseline(self):
        """Compare AI against a hard-coded Level-0 rule."""
        # Rule: Buy if > 0.5%, Sell if < -0.5%
        def l0_rule(row):
            chg = row['price_change_1h']
            if chg > 0.5: return 1 # Buy
            elif chg < -0.5: return -1 # Sell
            return 0 # Hold
            
        l0_actions = self.df.apply(l0_rule, axis=1)
        
        # Calculate L0 Accuracy (Simulated)
        # We need outcome. 'was_correct' is for the AI's action.
        # We need to know if Price went UP or DOWN.
        # 'price_direction' column exists: 'UP', 'DOWN', 'FLAT'
        
        direction_map = {'UP': 1, 'DOWN': -1, 'FLAT': 0}
        actual_dir = self.df['price_direction'].map(direction_map).fillna(0)
        
        # L0 correct if action matches direction (and action != 0)
        # or if action == 0 and direction == 0 (simplified)
        
        # Vectorized check
        # Correct if sign matches
        l0_correct = (l0_actions * actual_dir) > 0
        # Also count Hold as correct if Flat? Usually Hold is neutral. 
        # Let's align with 'was_correct' logic which usually penalizes inaction if opp exists, 
        # or just measures predictive power.
        # Assuming 'was_correct' in DB is 1 if Profit > 0 or Loss avoided.
        
        l0_acc = l0_correct.mean()
        ai_acc = self.df['was_correct'].mean()
        
        self.results["level0_comparison"] = {
            "ai_accuracy": round(ai_acc, 3),
            "level0_accuracy": round(l0_acc, 3),
            "ai_advantage": round(ai_acc - l0_acc, 3)
        }

    def generate_report(self):
        """Generate human-readable text report."""
        r = self.results
        
        report = f"""
BEHAVIORAL GAME THEORY ANALYSIS OF AI TRADING AGENT
===================================================
Generated: {pd.Timestamp.now()}
Data Points: {r['basic_stats']['total_decisions']}

1. BASIC STATISTICS
-------------------
Total Decisions: {r['basic_stats']['total_decisions']}
Executed Trades: {r['basic_stats']['executed_trades']}
Overall Win Rate: {r['basic_stats']['overall_win_rate']*100:.1f}%
Action Distribution: {r['basic_stats']['action_distribution']}

2. LEVEL-K MODEL ESTIMATION (Stahl & Wilson 1994)
-------------------------------------------------
The AI's behavior was fitted to Level-k models where k represents depth of strategic reasoning.

Level-0 (Trend): AIC {r['level_k_analysis']['level_0']['aic']}
Level-1 (Value): AIC {r['level_k_analysis']['level_1']['aic']}
Level-2 (Vol):   AIC {r['level_k_analysis']['level_2']['aic']}
Level-3 (Conf):  AIC {r['level_k_analysis']['level_3']['aic']}

BEST FIT: Level-{r['level_k_analysis']['best_level']}
Interpretation: {r['level_k_analysis']['interpretation']}

3. COGNITIVE HIERARCHY THEORY (Camerer et al. 2004)
---------------------------------------------------
Estimated Mean Thinking Steps (Tau): {r['cht_analysis']['optimal_tau']}
Inferred Level Distribution:
  Level-0: {r['cht_analysis']['level_distribution']['0']*100:.1f}%
  Level-1: {r['cht_analysis']['level_distribution']['1']*100:.1f}%
  Level-2: {r['cht_analysis']['level_distribution']['2']*100:.1f}%
  Level-3: {r['cht_analysis']['level_distribution']['3']*100:.1f}%

4. MODEL COMPARISON
-------------------
Best Model: {r['model_comparison']['best_model']}
Evidence Strength: {r['model_comparison']['evidence_strength']} (Delta AIC: {r['model_comparison']['delta_aic']})

5. RATIONALITY PROJECTION HYPOTHESIS (H1)
-----------------------------------------
Does the AI maintain higher strategic depth during rational market periods?

Rational Regime Win Rate: {r['rationality_projection']['rational_periods']['win_rate']*100:.1f}%
Emotional Regime Win Rate: {r['rationality_projection']['emotional_periods']['win_rate']*100:.1f}%

Rationality Projection Score (RPS): {r['rationality_projection']['rps_score']}
Hypothesis Supported: {r['rationality_projection']['hypothesis_supported']}

6. BASELINE COMPARISON
----------------------
AI vs Simple Level-0 Trend Follower:
AI Accuracy: {r['level0_comparison']['ai_accuracy']*100:.1f}%
L0 Accuracy: {r['level0_comparison']['level0_accuracy']*100:.1f}%
Advantage: {r['level0_comparison']['ai_advantage']*100:+.1f} points
"""
        return report

    def save_outputs(self):
        print("Saving results...")
        with open('analysis_results.json', 'w') as f:
            json.dump(self.results, f, indent=2)
            
        report = self.generate_report()
        with open('analysis_report.txt', 'w') as f:
            f.write(report)
            
        print("Done. Saved 'analysis_results.json' and 'analysis_report.txt'.")

def main():
    parser = argparse.ArgumentParser(description="Analyze AI Trading Data")
    parser.add_argument("--db", required=True, help="Path to sqlite database")
    args = parser.parse_args()
    
    analyzer = BehavioralAnalyzer(args.db)
    if analyzer.load_data():
        analyzer.basic_stats()
        analyzer.run_level_k_analysis()
        analyzer.run_cht_analysis()
        analyzer.compare_models()
        analyzer.analyze_rationality_projection()
        analyzer.level0_baseline()
        analyzer.save_outputs()

if __name__ == "__main__":
    main()
