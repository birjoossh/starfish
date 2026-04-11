"""ISS Backtest Validation Script.

Compares generated ISS parameters directly against forward T+20 and T+60 returns.
Produces output validation report to establish mathematical edge.
"""

import pandas as pd
import numpy as np
from config.database import get_engine
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def run_backtest():
    engine = get_engine()
    
    logger.info("Loading prices...")
    prices = pd.read_sql_query("SELECT trade_date, symbol, close FROM fact_eod_price ORDER BY symbol, trade_date", engine)
    
    logger.info("Loading signals...")
    signals = pd.read_sql_query("SELECT calc_date as trade_date, symbol, iss_score, signal_category FROM mart_stock_signals", engine)
    
    if len(prices) == 0 or len(signals) == 0:
        logger.error("No data found for backtest.")
        return
        
    prices['fwd_20d_close'] = prices.groupby('symbol')['close'].shift(-20)
    prices['fwd_60d_close'] = prices.groupby('symbol')['close'].shift(-60)
    
    prices['fwd_return_1m'] = (prices['fwd_20d_close'] - prices['close']) / prices['close']
    prices['fwd_return_3m'] = (prices['fwd_60d_close'] - prices['close']) / prices['close']
    
    merged = pd.merge(signals, prices[['trade_date', 'symbol', 'fwd_return_1m', 'fwd_return_3m']], on=['trade_date', 'symbol'])
    
    validation_set_1m = merged.dropna(subset=['fwd_return_1m']).copy()
    validation_set_3m = merged.dropna(subset=['fwd_return_3m']).copy()
    
    logger.info(f"Validation dataset size (1M Forward): {len(validation_set_1m)} rows")
    logger.info(f"Validation dataset size (3M Forward): {len(validation_set_3m)} rows")
    
    if len(validation_set_1m) == 0:
        logger.warning("Not enough data to calculate forward returns.")
        return
        
    print("\n" + "="*60)
    print("        🎯 ISS VALIDATION BACKTEST REPORT 🎯")
    print("="*60 + "\n")
    
    def qcut_safe(series, q, labels):
        return pd.qcut(series.rank(method='first'), q=q, labels=labels)
        
    validation_set_1m['iss_quintile'] = qcut_safe(validation_set_1m['iss_score'], 5, ['Bottom 20%', '20-40%', '40-60%', '60-80%', 'Top 20%'])
    if len(validation_set_3m) > 0:
        validation_set_3m['iss_quintile'] = qcut_safe(validation_set_3m['iss_score'], 5, ['Bottom 20%', '20-40%', '40-60%', '60-80%', 'Top 20%'])
    
    print("1. Median Performance by ISS Quintile (%)")
    print("-" * 50)
    
    perf = validation_set_1m.groupby('iss_quintile', observed=True)[['fwd_return_1m']].median() * 100
    if len(validation_set_3m) > 0:
        perf['fwd_return_3m'] = validation_set_3m.groupby('iss_quintile', observed=True)['fwd_return_3m'].median() * 100
        
    print(perf.round(2).to_string())
    print("\n")
    
    print("2. Median Performance by Signal Category (%)")
    print("-" * 50)
    
    sig_1m = validation_set_1m.groupby('signal_category')[['fwd_return_1m']].median() * 100
    counts = validation_set_1m.groupby('signal_category').size().rename("Count")
    cats = pd.concat([counts, sig_1m], axis=1)
    
    if len(validation_set_3m) > 0:
        sig_3m = validation_set_3m.groupby('signal_category')[['fwd_return_3m']].median() * 100
        cats['fwd_return_3m'] = sig_3m['fwd_return_3m']
        
    print(cats.round(2).to_string())
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    run_backtest()
