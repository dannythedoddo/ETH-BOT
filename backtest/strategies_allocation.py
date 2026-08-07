"""Variante di strategy_regime_pyramid che accetta uno SCHEMA di
allocazione esplicito: una lista di percentuali, una per ogni livello
di piramide.

Differenza chiave rispetto alla versione attuale del bot:
- Versione attuale: 90% del CASH RESIDUO ad ogni acquisto (quindi
  90%, poi 9%, poi 0.9%... del capitale iniziale)
- Questa versione: le percentuali sono calcolate sul CAPITALE
  DISPONIBILE ALL'INIZIO DEL TREND, quindi uno schema [0.5, 0.25,
  0.15, 0.10] significa davvero 50%, 25%, 15%, 10% del budget.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backtest_engine import Portfolio, compute_atr, compute_donchian, max_drawdown


def strategy_regime_pyramid_schedule(df, atr, allocation_schedule,
                                       regime_ma_period=1500, entry_period=25,
                                       atr_stop_mult=3.5, threshold_pct=0.02):
    """allocation_schedule: lista di frazioni del budget di trend.
    Es. [0.5, 0.25, 0.15, 0.10] = 50%, 25%, 15%, 10%."""
    ma_regime = df['Close'].rolling(regime_ma_period).mean()
    donch_upper, _ = compute_donchian(df, period=entry_period)

    pf = Portfolio(100.0)
    in_position = False
    trailing_stop = None
    last_action_price = df['Close'].iloc[0]
    n_pyramids = 0
    trend_budget = None  # capitale disponibile all'inizio del trend corrente

    prices = df['Close'].to_numpy()
    upps = donch_upper.to_numpy()
    atrs = atr.to_numpy()
    mas = ma_regime.to_numpy()
    n = len(prices)
    equity_curve = np.empty(n)

    for i in range(n):
        price = prices[i]
        a = atrs[i]
        upper = upps[i]
        ma = mas[i]
        if np.isnan(a) or np.isnan(upper) or np.isnan(ma):
            equity_curve[i] = pf.equity(price)
            continue

        th = price * threshold_pct
        bull_regime = price > ma
        moved_enough = abs(price - last_action_price) >= th

        if bull_regime:
            if (price >= upper and moved_enough and pf.cash > 1
                    and n_pyramids < len(allocation_schedule)):
                if not in_position:
                    trend_budget = pf.cash  # fissa il budget all'inizio del trend
                target_spend = trend_budget * allocation_schedule[n_pyramids]
                # non può spendere più del cash effettivamente disponibile
                spend = min(target_spend, pf.cash)
                frac_of_cash = spend / pf.cash if pf.cash > 0 else 0
                if spend >= 1:
                    pf.buy(price, frac_of_cash)
                    if not in_position:
                        in_position = True
                        trailing_stop = price - atr_stop_mult * a
                    n_pyramids += 1
                    last_action_price = price

            if in_position:
                new_stop = price - atr_stop_mult * a
                if new_stop > trailing_stop:
                    trailing_stop = new_stop
                if price <= trailing_stop and pf.eth * price > 1:
                    pf.sell(price, 1.0)
                    in_position = False
                    n_pyramids = 0
                    trend_budget = None
                    last_action_price = price
        else:
            if in_position and pf.eth * price > 1:
                pf.sell(price, 1.0)
                in_position = False
                n_pyramids = 0
                trend_budget = None
                last_action_price = price

        equity_curve[i] = pf.equity(price)

    pf.equity_curve = equity_curve
    return pf
