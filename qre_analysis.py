#!/usr/bin/env python3
"""
Quantal Response Equilibrium (QRE) Analysis Tool for Behavioral Game Theory Research.
Analyzes AI trading bot decisions to test if behavior matches QRE equilibrium play.

References:
- QRE: McKelvey, R. D., & Palfrey, T. R. (1995). Quantal response equilibria for normal form games. Games and Economic Behavior, 10(1), 6-38.
- Level-k: Stahl, D. O., & Wilson, P. W. (1994). Experimental evidence on players' models of other players. Journal of Economic Behavior & Organization, 25(3), 309-327.
- AIC: Akaike, H. (1974). A new look at the statistical model identification. IEEE Transactions on Automatic Control, 19(6), 716-723.
- Vuong: Vuong, Q. H. (1989). Likelihood ratio tests for model selection and non-nested hypotheses. Econometrica, 57(2), 307-333.
"""

import sqlite3
import pandas as pd
import numpy as np
import argparse
import json
import sys
from scipy.optimize import minimize_scalar
from scipy.stats import norm

class QREAnalyzer:
    def __init__(self, db_path, levelk_results_path):
        self.db_path = db_path
        self.levelk_results_path = levelk_results_path
        self.df = None
        self.levelk_results = None
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
            # Note: The prompt specifies 'BUY': 1, 'SELL': -1, 'HOLD': 0
            action_map = {'BUY': 1, 'SELL': -1, 'HOLD': 0}
            self.df['action_num'] = self.df['action'].map(action_map).fillna(0).astype(int)
            
            # Ensure necessary columns are float
            cols_to_float = ['price_change_1h', 'price_change_24h', 'fear_greed_index']
            for col in cols_to_float:
                if col in self.df.columns:
                    self.df[col] = pd.to_numeric(self.df[col], errors='coerce').fillna(0.0)

            print(f"Loaded {len(self.df)} records.")
            return True
        except Exception as e:
            print(f"Error loading data: {e}")
            return False

    def load_levelk_results(self):
        """Load existing Level-k results for comparison."""
        print(f"Loading Level-k results from {self.levelk_results_path}...")
        try:
            with open(self.levelk_results_path, 'r') as f:
                self.levelk_results = json.load(f)
            return True
        except Exception as e:
            print(f"Error loading Level-k results: {e}")
            return False

    def qre_expected_utility(self, action: int, state: dict) -> float:
        """
        QRE expected utility for trading. 
        
        Parameters:
            action: 1 (BUY), -1 (SELL), 0 (HOLD)
            state: {'return': recent_return, 'volatility': ...}
        """
        r = state['return']  # Recent return
        
        # Market equilibrium assumption: slight momentum
        momentum_bias = 0.52  # Slight positive autocorrelation
        
        if r > 0:
            p_up = momentum_bias
            p_down = 1 - momentum_bias
        elif r < 0:
            p_up = 1 - momentum_bias
            p_down = momentum_bias
        else:
            p_up = 0.5
            p_down = 0.5
        
        # Expected move magnitude (use recent volatility or fixed)
        expected_move = abs(r) if abs(r) > 0.001 else 0.005
        
        # Expected utility for each action
        if action == 1:  # BUY
            eu = p_up * expected_move - p_down * expected_move
        elif action == -1:  # SELL
            eu = p_down * expected_move - p_up * expected_move
        else:  # HOLD
            eu = 0
        
        return eu

    def qre_choice_probability(self, action: int, state: dict, lambda_qre: float) -> float:
        """
        QRE probability of choosing action. 
        
        Formula (McKelvey & Palfrey 1995):
            P(a) = exp(λ·EU(a)) / Σ exp(λ·EU(a'))
        """
        actions = [1, -1, 0]  # BUY, SELL, HOLD
        
        eus = {a: self.qre_expected_utility(a, state) for a in actions}
        
        # Softmax with numerical stability
        max_eu = max(eus.values())
        # Clip to avoid overflow/underflow in exp
        exp_values = {a: np.exp(np.clip(lambda_qre * (eu - max_eu), -500, 500)) 
                      for a, eu in eus.items()}
        
        total = sum(exp_values.values())
        
        if total == 0 or np.isnan(total):
            return 1/3
        
        return exp_values[action] / total

    def qre_log_likelihood(self, df: pd.DataFrame, lambda_qre: float) -> float:
        """
        Calculate log-likelihood for QRE model. 
        
        L(λ) = Σ log P_QRE(a_t | s_t, λ)
        """
        log_likelihood = 0.0
        
        # Vectorizing this for performance would be better, but loop is safer for direct translation of logic
        # For 72k rows, a loop might be slow. Let's try to optimize slightly or accept it.
        # Given the complexity of EU calc (dependent on sign of return), let's stick to loop for correctness first.
        
        # Actually, let's extract columns to numpy arrays to speed up access
        returns = df['price_change_1h'].values / 100.0
        actions = df['action_num'].values
        
        # Pre-calculate EUs since they don't depend on lambda
        # This is a huge optimization.
        
        # Arrays for EUs of BUY, SELL, HOLD
        n = len(df)
        eu_buy = np.zeros(n)
        eu_sell = np.zeros(n)
        eu_hold = np.zeros(n)
        
        # Vectorized EU calculation
        momentum_bias = 0.52
        
        # Mask for return > 0
        pos_mask = returns > 0
        neg_mask = returns < 0
        zero_mask = returns == 0
        
        p_up = np.zeros(n)
        p_down = np.zeros(n)
        
        p_up[pos_mask] = momentum_bias
        p_down[pos_mask] = 1 - momentum_bias
        
        p_up[neg_mask] = 1 - momentum_bias
        p_down[neg_mask] = momentum_bias
        
        p_up[zero_mask] = 0.5
        p_down[zero_mask] = 0.5
        
        expected_move = np.where(np.abs(returns) > 0.001, np.abs(returns), 0.005)
        
        eu_buy = p_up * expected_move - p_down * expected_move
        eu_sell = p_down * expected_move - p_up * expected_move
        eu_hold = np.zeros(n)
        
        # Now calculate log likelihood using vectorization
        # Stack EUs: shape (N, 3) -> [BUY, SELL, HOLD] to match action indices?
        # My action map: BUY=1, SELL=-1, HOLD=0.
        # Let's map to indices: 0->HOLD, 1->BUY, 2->SELL (arbitrary, just needs consistency)
        # Or let's just use the direct values.
        
        # Let's align with the order: [BUY (1), SELL (-1), HOLD (0)]
        all_eus = np.column_stack([eu_buy, eu_sell, eu_hold])
        
        # Calculate max EU for stability
        max_eus = np.max(all_eus, axis=1, keepdims=True)
        
        # Calculate exp values
        exp_vals = np.exp(np.clip(lambda_qre * (all_eus - max_eus), -500, 500))
        sum_exp = np.sum(exp_vals, axis=1)
        
        # Select prob of chosen action
        # Map actions to indices in all_eus: 1->0, -1->1, 0->2
        # action_num is 1, -1, 0
        
        # Create an index mapper
        # BUY(1) -> col 0
        # SELL(-1) -> col 1
        # HOLD(0) -> col 2
        
        col_indices = np.zeros(n, dtype=int)
        col_indices[actions == 1] = 0
        col_indices[actions == -1] = 1
        col_indices[actions == 0] = 2
        
        chosen_exp = exp_vals[np.arange(n), col_indices]
        probs = chosen_exp / sum_exp
        
        # Avoid log(0)
        probs = np.maximum(probs, 1e-15)
        
        log_likelihood = np.sum(np.log(probs))
        return log_likelihood

    def estimate_qre(self, df: pd.DataFrame) -> dict:
        """Estimate QRE λ parameter using MLE."""
        print(f"Estimating QRE for {len(df)} observations...")
        
        # Grid search
        best_ll = -np.inf
        best_lambda = 1.0
        
        # Reduced grid for speed, relying on minimize_scalar for refinement
        grid = [0.01, 0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0]
        
        for lam in grid:
            ll = self.qre_log_likelihood(df, lam)
            if ll > best_ll:
                best_ll = ll
                best_lambda = lam
        
        # Refine
        def neg_ll(lam):
            if lam <= 0:
                return 1e10
            return -self.qre_log_likelihood(df, lam)
        
        # Bounded optimization around best_lambda
        # Expand bounds to cover likely range
        lower = max(0.001, best_lambda / 10)
        upper = min(500.0, best_lambda * 10)
        
        result = minimize_scalar(neg_ll, bounds=(lower, upper), method='bounded')
        
        if -result.fun > best_ll:
            best_lambda = result.x
            best_ll = -result.fun
        
        # Calculate AIC, BIC
        n = len(df)
        k = 1  # Only λ parameter
        aic = 2 * k - 2 * best_ll
        bic = k * np.log(n) - 2 * best_ll
        
        return {
            'optimal_lambda': float(best_lambda),
            'log_likelihood': float(best_ll),
            'aic': float(aic),
            'bic': float(bic),
            'n_observations': n
        }

    def _logit_prob_lk(self, utilities, lambda_param):
        """Helper for Level-k prob calc in Vuong test (reused logic)."""
        scaled_u = utilities * lambda_param
        max_u = np.max(scaled_u, axis=1, keepdims=True)
        exp_u = np.exp(scaled_u - max_u)
        sum_exp_u = np.sum(exp_u, axis=1, keepdims=True)
        probs = exp_u / sum_exp_u
        return probs

    def _calculate_lk_utilities(self, k, df):
        """Re-implementation of Level-k utility calc for Vuong test."""
        n = len(df)
        utils = np.zeros((n, 3)) # cols: SELL(-1), HOLD(0), BUY(1) - Need to match this order?
        # Note: In analyze_trading_data.py, utils[:, 0]=SELL, utils[:, 1]=HOLD, utils[:, 2]=BUY.
        # My QRE vectorization used [BUY, SELL, HOLD]. I must match carefully.
        
        # Let's standardise on [BUY, SELL, HOLD] for Vuong comparison arrays
        
        r = df['price_change_1h'].values / 100.0
        rsi_sig = (50 - df['rsi_14'].values) / 50.0
        bb_sig = (0.5 - df['bb_position'].values) * 2.0
        
        signal = np.zeros(n)
        if k == 0: signal = r
        elif k == 1: signal = r + rsi_sig
        elif k == 2: signal = r + rsi_sig + bb_sig
        elif k == 3: 
             vol_ratio = np.clip(df['volume_ratio'].values, 0, 5) / 5.0
             signal = (r + rsi_sig + bb_sig) * (1 + vol_ratio)
             
        # Level-k logic from other file:
        # U(Sell) = -signal
        # U(Hold) = 0
        # U(Buy) = signal
        
        # Return in order [BUY, SELL, HOLD] to match my QRE structure
        utils_ordered = np.column_stack([signal, -signal, np.zeros(n)])
        return utils_ordered

    def vuong_test_qre_levelk(self, df: pd.DataFrame, qre_result: dict, levelk_info: dict) -> dict:
        """
        Vuong (1989) test for non-nested model comparison.
        """
        qre_lambda = qre_result['optimal_lambda']
        
        # Level-k params
        lk_level = levelk_info.get('best_level', 1) # Default to 1 if missing
        
        # Get lambda for the best level
        best_level_key = f"level_{lk_level}"
        if best_level_key in levelk_info:
            lk_lambda = levelk_info[best_level_key]['lambda']
        else:
            # Fallback if structure is different
             lk_lambda = 0.6271 
        
        print(f"Vuong Test: Comparing QRE(λ={qre_lambda:.2f}) vs Level-{lk_level}(λ={lk_lambda:.2f})")
        
        # Calculate probabilities for each observation
        # QRE Probs
        # Reuse vectorized logic
        returns = df['price_change_1h'].values / 100.0
        actions = df['action_num'].values
        n = len(df)
        
        # QRE EUs
        momentum_bias = 0.52
        p_up = np.where(returns > 0, momentum_bias, np.where(returns < 0, 1-momentum_bias, 0.5))
        p_down = 1 - p_up
        expected_move = np.where(np.abs(returns) > 0.001, np.abs(returns), 0.005)
        
        eu_buy = p_up * expected_move - p_down * expected_move
        eu_sell = p_down * expected_move - p_up * expected_move
        eu_hold = np.zeros(n)
        
        all_eus_qre = np.column_stack([eu_buy, eu_sell, eu_hold]) # [BUY, SELL, HOLD]
        
        # QRE Probs
        max_eus_qre = np.max(all_eus_qre, axis=1, keepdims=True)
        exp_vals_qre = np.exp(np.clip(qre_lambda * (all_eus_qre - max_eus_qre), -500, 500))
        sum_exp_qre = np.sum(exp_vals_qre, axis=1)
        
        # Level-k Probs
        utils_lk = self._calculate_lk_utilities(lk_level, df) # [BUY, SELL, HOLD]
        max_u_lk = np.max(utils_lk * lk_lambda, axis=1, keepdims=True)
        exp_vals_lk = np.exp(np.clip(utils_lk * lk_lambda - max_u_lk, -500, 500))
        sum_exp_lk = np.sum(exp_vals_lk, axis=1)
        
        # Select prob of chosen action
        # Actions: BUY(1), SELL(-1), HOLD(0) -> Indices [0, 1, 2]
        col_indices = np.zeros(n, dtype=int)
        col_indices[actions == 1] = 0
        col_indices[actions == -1] = 1
        col_indices[actions == 0] = 2
        
        p_qre = exp_vals_qre[np.arange(n), col_indices] / sum_exp_qre
        p_lk = exp_vals_lk[np.arange(n), col_indices] / sum_exp_lk
        
        # Avoid log(0)
        p_qre = np.maximum(p_qre, 1e-15)
        p_lk = np.maximum(p_lk, 1e-15)
        
        # Log likelihood ratios
        log_ratios = np.log(p_qre) - np.log(p_lk)
        
        mean_lr = np.mean(log_ratios)
        std_lr = np.std(log_ratios, ddof=1)
        
        z_stat = np.sqrt(n) * mean_lr / std_lr if std_lr > 0 else 0
        p_value = 2 * (1 - norm.cdf(abs(z_stat)))
        
        if abs(z_stat) < 1.96:
            conclusion = "Models are statistically equivalent"
            winner = "Tie"
        elif z_stat > 1.96:
            conclusion = "QRE significantly better than Level-k"
            winner = "QRE"
        else:
            conclusion = "Level-k significantly better than QRE"
            winner = "Level-k"
            
        return {
            'z_statistic': float(z_stat),
            'p_value': float(p_value),
            'conclusion': conclusion,
            'winner': winner
        }

    def run_analysis(self):
        """Main execution flow."""
        if not self.load_data(): return
        if not self.load_levelk_results(): return
        
        print("\n--- Starting QRE Analysis ---")
        
        # 1. Estimate QRE
        qre_result = self.estimate_qre(self.df)
        self.results['qre_analysis'] = qre_result
        
        # Interpretation
        lam = qre_result['optimal_lambda']
        if lam < 0.5: interp = "High noise (random behavior)"
        elif lam < 2.0: interp = "Moderate precision"
        else: interp = "High precision (rational)"
        self.results['qre_analysis']['interpretation'] = interp
        
        print(f"Optimal Lambda: {lam:.4f}")
        print(f"Log-Likelihood: {qre_result['log_likelihood']:.2f}")
        print(f"AIC: {qre_result['aic']:.2f}")
        
        # 2. Compare with Level-k
        lk_info = self.levelk_results.get('level_k_analysis', {})
        cht_info = self.levelk_results.get('cht_analysis', {})
        
        # Get best LK AIC
        best_level = lk_info.get('best_level', 1)
        lk_aic = lk_info.get(f"level_{best_level}", {}).get('aic', 0)
        
        cht_aic = cht_info.get('aic', 0)
        
        delta_aic = abs(qre_result['aic'] - lk_aic)
        winner_aic = 'QRE' if qre_result['aic'] < lk_aic else 'Level-k'
        
        if delta_aic < 2: evidence = "No meaningful difference"
        elif delta_aic < 4: evidence = "Weak evidence"
        elif delta_aic < 7: evidence = "Moderate evidence"
        else: evidence = "Strong evidence"
        
        # Vuong Test
        vuong = self.vuong_test_qre_levelk(self.df, qre_result, lk_info)
        
        self.results['model_comparison'] = {
            'qre_aic': qre_result['aic'],
            'levelk_aic': lk_aic,
            'cht_aic': cht_aic,
            'best_model': winner_aic,
            'delta_aic_qre_vs_levelk': float(delta_aic),
            'evidence_strength': evidence,
            'vuong_test': vuong
        }
        
        # 3. Regime Analysis
        print("\n--- Running Regime Analysis ---")
        emotional = self.df[(self.df['fear_greed_index'] < 30) | (self.df['fear_greed_index'] > 70)]
        rational = self.df[(self.df['fear_greed_index'] >= 30) & (self.df['fear_greed_index'] <= 70)]
        
        regime_results = {}
        
        if len(emotional) > 100:
            print(f"Emotional Regime ({len(emotional)} obs)")
            res_em = self.estimate_qre(emotional)
            regime_results['emotional'] = {'optimal_lambda': res_em['optimal_lambda'], 'n': res_em['n_observations']}
        
        if len(rational) > 100:
            print(f"Rational Regime ({len(rational)} obs)")
            res_ra = self.estimate_qre(rational)
            regime_results['rational'] = {'optimal_lambda': res_ra['optimal_lambda'], 'n': res_ra['n_observations']}
            
        if 'emotional' in regime_results and 'rational' in regime_results:
            ratio = regime_results['rational']['optimal_lambda'] / regime_results['emotional']['optimal_lambda']
            regime_results['lambda_ratio'] = float(ratio)
            
            if ratio > 1.2: reg_interp = "AI more precise in rational markets"
            elif ratio < 0.8: reg_interp = "AI more precise in emotional markets"
            else: reg_interp = "Similar precision across regimes"
            
            regime_results['interpretation'] = reg_interp
            
        self.results['regime_analysis'] = regime_results
        
        # 4. Final Conclusion
        if winner_aic == 'Level-k':
            conclusion = "AI behavior better explained by Level-k bounded reasoning than QRE equilibrium play. The AI is not trying to reach equilibrium with noise; it's using a fixed Level-k strategy."
        else:
            conclusion = "AI behavior is better explained by QRE, suggesting it attempts to reach market equilibrium with some noise."
            
        self.results['combined_interpretation'] = conclusion
        
        # Save results
        self.save_outputs()

    def generate_report(self):
        """Generate human-readable text report."""
        r = self.results
        mc = r['model_comparison']
        qa = r['qre_analysis']
        ra = r['regime_analysis']
        
        report = f"""
================================================================================
QUANTAL RESPONSE EQUILIBRIUM (QRE) ANALYSIS
Based on McKelvey & Palfrey (1995)
================================================================================

PARAMETER ESTIMATION
  Optimal λ: {qa['optimal_lambda']:.4f}
  Log-Likelihood: {qa['log_likelihood']:.1f}
  AIC: {qa['aic']:.1f}
  BIC: {qa['bic']:.1f}

INTERPRETATION
  {qa['interpretation']}
  (λ < 1 suggests noisy decisions, High λ suggests Nash behavior)

--------------------------------------------------------------------------------
MODEL COMPARISON
--------------------------------------------------------------------------------
  Model          AIC
  Level-k        {mc['levelk_aic']:.1f}
  CHT            {mc['cht_aic']:.1f}
  QRE            {mc['qre_aic']:.1f}

  Best Model: {mc['best_model']} (ΔAIC = {mc['delta_aic_qre_vs_levelk']:.1f} vs QRE)
  Evidence: {mc['evidence_strength']}
  
  Vuong Test: Z = {mc['vuong_test']['z_statistic']:.2f}, p = {mc['vuong_test']['p_value']:.4f}
  Conclusion: {mc['vuong_test']['conclusion']}

--------------------------------------------------------------------------------
REGIME ANALYSIS
--------------------------------------------------------------------------------
  Emotional markets (F&G < 30 or > 70):
    λ = {ra.get('emotional', {}).get('optimal_lambda', 'N/A')} (n={ra.get('emotional', {}).get('n', 0)})
    
  Rational markets (30 ≤ F&G ≤ 70):
    λ = {ra.get('rational', {}).get('optimal_lambda', 'N/A')} (n={ra.get('rational', {}).get('n', 0)})
    
  Ratio: {ra.get('lambda_ratio', 'N/A')}
  Interpretation: {ra.get('interpretation', 'N/A')}

================================================================================
CONCLUSION
================================================================================
{r['combined_interpretation']}
"""
        return report

    def save_outputs(self):
        print("Saving results...")
        with open('analysis_qre_results.json', 'w') as f:
            json.dump(self.results, f, indent=2)
        
        # Read existing report to append or create new section
        try:
            with open('analysis_report.txt', 'r') as f:
                existing_report = f.read()
        except FileNotFoundError:
            existing_report = ""
            
        new_section = self.generate_report()
        
        # Append or replace? 
        # Let's create a separate report file for QRE to avoid messing up the original,
        # but also append to the main report if possible.
        # The prompt says "Output to same directory as other analysis files".
        
        with open('analysis_qre_report.txt', 'w') as f:
            f.write(new_section)
            
        # Also append to main report
        with open('analysis_report.txt', 'a') as f:
            f.write("\n\n" + new_section)
            
        print("Done. Saved 'analysis_qre_results.json' and updated 'analysis_report.txt'.")

def main():
    parser = argparse.ArgumentParser(description="Analyze AI Trading QRE")
    parser.add_argument("--db", required=True, help="Path to sqlite database")
    parser.add_argument("--levelk-results", required=True, help="Path to level-k results json")
    args = parser.parse_args()
    
    analyzer = QREAnalyzer(args.db, args.levelk_results)
    analyzer.run_analysis()

if __name__ == "__main__":
    main()
