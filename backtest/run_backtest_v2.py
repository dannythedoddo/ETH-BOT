"""Riproduce il backtest della strategia attuale sul motore CORRETTO.

Uso:
    python backtest/run_backtest_v2.py --csv dati_15m.csv
    python backtest/run_backtest_v2.py --csv dati_15m.csv --split 2024-08-01
"""
import argparse, sys, os
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine_v2 import load_data, compute_atr, max_drawdown, cagr
from strategies_v2 import regime_pyramid, buy_hold


def report(d, atr, label, rp, ep, am, th):
    yrs = (d['timestamp'].iloc[-1] - d['timestamp'].iloc[0]).days / 365.25
    pf = regime_pyramid(d, atr, rp, ep, am, th, alloc=(1.0,))
    eq = pf.equity_curve
    bh = buy_hold(d)
    print(f"\n--- {label} ({d['timestamp'].iloc[0].date()} -> {d['timestamp'].iloc[-1].date()}, {yrs:.1f} anni) ---")
    print(f"  Strategia : {eq[-1]:7.2f}€  CAGR {cagr(eq, yrs):+6.2f}%  MaxDD {max_drawdown(eq)*100:6.1f}%  trade {pf.trades}")
    print(f"  Buy&Hold  : {bh[-1]:7.2f}€  CAGR {cagr(bh, yrs):+6.2f}%  MaxDD {max_drawdown(bh)*100:6.1f}%")
    return d, eq


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="CSV OHLCV (qualsiasi timeframe, verrà ricampionato a 4h)")
    ap.add_argument("--split", default="2024-08-01", help="data di separazione ottimizzazione/verifica")
    ap.add_argument("--regime-ma", type=int, default=180)
    ap.add_argument("--entry-period", type=int, default=20)
    ap.add_argument("--atr-mult", type=float, default=5.0)
    ap.add_argument("--threshold-pct", type=float, default=0.02)
    a = ap.parse_args()

    raw = load_data(a.csv)
    d = raw.set_index('timestamp').resample('4h').agg(
        {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
    ).dropna().reset_index()

    print(f"Parametri: regime_MA={a.regime_ma} (4h) | entry={a.entry_period} | ATR_stop={a.atr_mult} | soglia={a.threshold_pct:.1%}")
    report(d, compute_atr(d, 14), "PERIODO COMPLETO", a.regime_ma, a.entry_period, a.atr_mult, a.threshold_pct)

    split = pd.Timestamp(a.split, tz='UTC')
    IS = d[d['timestamp'] < split].reset_index(drop=True)
    OOS = d[d['timestamp'] >= split].reset_index(drop=True)
    if len(IS) > 200 and len(OOS) > 200:
        report(IS, compute_atr(IS, 14), "IN-SAMPLE (ottimizzazione)", a.regime_ma, a.entry_period, a.atr_mult, a.threshold_pct)
        report(OOS, compute_atr(OOS, 14), "OUT-OF-SAMPLE (verifica)", a.regime_ma, a.entry_period, a.atr_mult, a.threshold_pct)


if __name__ == "__main__":
    main()
