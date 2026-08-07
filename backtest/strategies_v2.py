"""Strategie riscritte sul motore corretto (engine_v2)."""
import numpy as np
import pandas as pd
from engine_v2 import (Portfolio, compute_atr, donchian_upper, donchian_lower,
                        regime_ma, max_drawdown, INITIAL_CAPITAL)


def regime_pyramid(df, atr, regime_p=1500, entry_p=25, atr_mult=3.5,
                    th_pct=0.02, alloc=(1.0,)):
    """Regime filter (MA lunga) + breakout Donchian + trailing stop ATR,
    con piramidazione secondo lo schema `alloc`."""
    ma = regime_ma(df, regime_p).to_numpy()
    upp = donchian_upper(df, entry_p).to_numpy()
    prices = df['Close'].to_numpy()
    atrs = atr.to_numpy()
    n = len(prices)

    pf = Portfolio()
    inpos = False; ts = None; lap = prices[0]; npyr = 0; budget = None
    eq = np.empty(n)

    for i in range(n):
        p = prices[i]; a = atrs[i]; u = upp[i]; m = ma[i]
        if np.isnan(a) or np.isnan(u) or np.isnan(m):
            eq[i] = pf.equity(p); continue

        moved = abs(p - lap) >= p * th_pct
        if p > m:  # regime bull
            if p >= u and moved and pf.cash > 1 and npyr < len(alloc):
                if not inpos:
                    budget = pf.cash
                spend = min(budget * alloc[npyr], pf.cash)
                if spend >= 1 and pf.buy(p, spend / pf.cash):
                    if not inpos:
                        inpos = True; ts = p - atr_mult * a
                    npyr += 1; lap = p
            if inpos:
                ns = p - atr_mult * a
                if ns > ts: ts = ns
                if p <= ts and pf.sell(p, 1.0):
                    inpos = False; npyr = 0; budget = None; lap = p
        else:      # regime bear -> fuori
            if inpos and pf.sell(p, 1.0):
                inpos = False; npyr = 0; budget = None; lap = p
        eq[i] = pf.equity(p)

    pf.equity_curve = eq
    return pf


def trend_following(df, atr, entry_p=30, atr_mult=3.0, th_pct=0.02, frac=1.0):
    """Breakout Donchian + trailing stop ATR, senza filtro di regime."""
    upp = donchian_upper(df, entry_p).to_numpy()
    prices = df['Close'].to_numpy()
    atrs = atr.to_numpy()
    n = len(prices)

    pf = Portfolio()
    inpos = False; ts = None; lap = prices[0]
    eq = np.empty(n)

    for i in range(n):
        p = prices[i]; a = atrs[i]; u = upp[i]
        if np.isnan(a) or np.isnan(u):
            eq[i] = pf.equity(p); continue
        moved = abs(p - lap) >= p * th_pct
        if not inpos:
            if p >= u and moved and pf.buy(p, frac):
                inpos = True; ts = p - atr_mult * a; lap = p
        else:
            ns = p - atr_mult * a
            if ns > ts: ts = ns
            if p <= ts and pf.sell(p, 1.0):
                inpos = False; lap = p
        eq[i] = pf.equity(p)

    pf.equity_curve = eq
    return pf


def ma_regime_only(df, regime_p=1500, frac=1.0):
    """Strategia minimale di riferimento: dentro se prezzo > MA lunga,
    fuori altrimenti. Nessun breakout, nessun trailing stop.
    Serve come benchmark: se le strategie complesse non la battono,
    la complessità non sta aggiungendo valore."""
    ma = regime_ma(df, regime_p).to_numpy()
    prices = df['Close'].to_numpy()
    n = len(prices)

    pf = Portfolio()
    inpos = False
    eq = np.empty(n)

    for i in range(n):
        p = prices[i]; m = ma[i]
        if np.isnan(m):
            eq[i] = pf.equity(p); continue
        if p > m and not inpos:
            if pf.buy(p, frac): inpos = True
        elif p <= m and inpos:
            if pf.sell(p, 1.0): inpos = False
        eq[i] = pf.equity(p)

    pf.equity_curve = eq
    return pf


def buy_hold(df):
    prices = df['Close'].to_numpy()
    return INITIAL_CAPITAL * prices / prices[0]
