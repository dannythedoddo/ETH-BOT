"""
Riproduce il backtest della strategia Regime-Adaptive Pyramid sui dati
storici. Utile per verificare che i risultati riportati nel README
siano riproducibili, o per ri-testare dopo aver modificato i parametri
in bot/config.py.

Uso:
    python backtest/run_backtest.py --csv path/to/eth_15m.csv
"""
import argparse
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from backtest_engine import load_data, compute_atr, max_drawdown
from strategies import get_threshold_series, strategy_regime_pyramid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="Path al CSV OHLCV (timestamp,Open,High,Low,Close,Volume)")
    parser.add_argument("--regime-ma", type=int, default=1500)
    parser.add_argument("--entry-period", type=int, default=25)
    parser.add_argument("--atr-mult", type=float, default=3.5)
    parser.add_argument("--threshold-pct", type=float, default=0.02)
    parser.add_argument("--pyramid-fraction", type=float, default=0.90)
    parser.add_argument("--max-pyramids", type=int, default=10)
    args = parser.parse_args()

    df = load_data(args.csv)
    atr = compute_atr(df, period=14)
    th_series = get_threshold_series(df, mode="pct", pct=args.threshold_pct)

    pf = strategy_regime_pyramid(
        df, th_series, atr,
        regime_ma_period=args.regime_ma,
        entry_period=args.entry_period,
        atr_stop_mult=args.atr_mult,
        pyramid_fraction=args.pyramid_fraction,
        max_pyramids=args.max_pyramids,
    )

    eq = np.array(pf.equity_curve)
    years = (df["timestamp"].iloc[-1] - df["timestamp"].iloc[0]).days / 365.25
    total_ret = eq[-1] / 100
    cagr = (total_ret ** (1 / years) - 1) * 100
    mdd = max_drawdown(eq) * 100
    bh_final = 100 * df["Close"].iloc[-1] / df["Close"].iloc[0]

    print(f"Periodo:            {df['timestamp'].iloc[0]} -> {df['timestamp'].iloc[-1]} ({years:.1f} anni)")
    print(f"Equity finale:       {eq[-1]:.2f}€")
    print(f"Rendimento totale:   {(total_ret-1)*100:+.1f}%")
    print(f"CAGR:                {cagr:+.1f}%/anno")
    print(f"Max Drawdown:        {mdd:.1f}%")
    print(f"N. trade:            {pf.trades}")
    print(f"Buy&Hold equivalente: {bh_final:.2f}€ ({(bh_final/100-1)*100:+.1f}%)")


if __name__ == "__main__":
    main()
