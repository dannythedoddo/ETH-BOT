"""
4 strategie non-predittive e adattive, ciascuna con 3 varianti di soglia:
- fixed: soglia fissa in € (50€ come richiesto originariamente)
- pct: soglia dinamica in % del prezzo corrente
- atr: soglia basata su ATR (si adatta alla volatilità corrente)
"""
import numpy as np
import pandas as pd
from backtest_engine import Portfolio, compute_atr, compute_bollinger, compute_donchian, max_drawdown, FEE_RATE

def get_threshold_series(df, mode, fixed_eur=50, pct=0.015, atr_mult=1.0, atr=None):
    """Ritorna una serie di soglie assolute in € per ogni riga."""
    if mode == 'fixed':
        return pd.Series(fixed_eur, index=df.index)
    elif mode == 'pct':
        return df['Close'] * pct
    elif mode == 'atr':
        return atr * atr_mult
    else:
        raise ValueError(mode)

# ---------------------------------------------------------------------
# STRATEGIA 1: GRID TRADING DINAMICO
# Griglia centrata sul prezzo di riferimento (ultimo trade), ricalcolata
# man mano che il prezzo si muove. Compra a ogni step giù, vende a ogni step su.
# ---------------------------------------------------------------------
def strategy_grid(df, threshold_series, trade_fraction=0.20):
    pf = Portfolio(100.0)
    ref_price = df['Close'].iloc[0]
    for i, row in df.iterrows():
        price = row['Close']
        th = threshold_series.iloc[i]
        if pd.isna(th) or th <= 0:
            pf.record(price)
            continue
        if price <= ref_price - th and pf.cash > 1:
            pf.buy(price, trade_fraction)
            ref_price = price
        elif price >= ref_price + th and pf.eth * price > 1:
            pf.sell(price, trade_fraction)
            ref_price = price
        pf.record(price)
    return pf

# ---------------------------------------------------------------------
# STRATEGIA 2: MEAN REVERSION SU BANDE DI BOLLINGER
# Compra quando tocca banda inferiore, vende su banda superiore.
# La soglia (threshold) qui filtra i falsi segnali: serve un movimento
# minimo di `th` rispetto all'ultimo trade per rientrare in azione.
# ---------------------------------------------------------------------
def strategy_mean_reversion(df, threshold_series, trade_fraction=0.30, period=20):
    ma, upper, lower = compute_bollinger(df, period=period)
    pf = Portfolio(100.0)
    last_trade_price = df['Close'].iloc[0]

    prices = df['Close'].to_numpy()
    ths = threshold_series.to_numpy()
    lowers = lower.to_numpy()
    uppers = upper.to_numpy()
    n = len(prices)
    equity_curve = np.empty(n)

    for i in range(n):
        price = prices[i]
        th = ths[i]
        lo = lowers[i]
        up = uppers[i]
        if np.isnan(th) or np.isnan(lo) or th <= 0:
            equity_curve[i] = pf.equity(price)
            continue
        moved_enough = abs(price - last_trade_price) >= th
        if price <= lo and moved_enough and pf.cash > 1:
            pf.buy(price, trade_fraction)
            last_trade_price = price
        elif price >= up and moved_enough and pf.eth * price > 1:
            pf.sell(price, trade_fraction)
            last_trade_price = price
        equity_curve[i] = pf.equity(price)
    pf.equity_curve = equity_curve
    return pf

# ---------------------------------------------------------------------
# STRATEGIA 3: TREND FOLLOWING con DONCHIAN BREAKOUT + ATR TRAILING STOP
# Entra long alla rottura del massimo N periodi, esce con trailing stop ATR.
# Non prevede: segue il movimento già in corso.
# ---------------------------------------------------------------------
def strategy_trend_following(df, threshold_series, atr, trade_fraction=0.40, period=20, atr_stop_mult=2.0):
    donch_upper, donch_lower = compute_donchian(df, period=period)
    pf = Portfolio(100.0)
    in_position = False
    trailing_stop = None
    last_action_price = df['Close'].iloc[0]

    prices = df['Close'].to_numpy()
    ths = threshold_series.to_numpy()
    upps = donch_upper.to_numpy()
    atrs = atr.to_numpy()
    n = len(prices)
    equity_curve = np.empty(n)

    for i in range(n):
        price = prices[i]
        th = ths[i]
        a = atrs[i]
        upper = upps[i]
        if np.isnan(th) or np.isnan(upper) or np.isnan(a):
            equity_curve[i] = pf.equity(price)
            continue
        moved_enough = abs(price - last_action_price) >= th

        if not in_position:
            if price >= upper and moved_enough and pf.cash > 1:
                pf.buy(price, trade_fraction)
                in_position = True
                trailing_stop = price - atr_stop_mult * a
                last_action_price = price
        else:
            new_stop = price - atr_stop_mult * a
            if new_stop > trailing_stop:
                trailing_stop = new_stop
            if price <= trailing_stop and pf.eth * price > 1:
                pf.sell(price, 1.0)
                in_position = False
                last_action_price = price
        equity_curve[i] = pf.equity(price)
    pf.equity_curve = equity_curve
    return pf


# ---------------------------------------------------------------------
# STRATEGIA 5: REGIME-ADAPTIVE PYRAMID TREND
# Filtro di regime (MA lunga) decide bull/bear. In bull: entra e PIRAMIDA
# (aggiunge posizione) ad ogni nuovo breakout di un canale corto, così
# non si ferma alla prima entrata come il trend-following classico e
# cattura più del rally. Trailing stop ATR segue sempre il prezzo.
# In bear: esce SUBITO e integralmente, resta in liquidità finché il
# regime non torna bull. Nessuna previsione: reagisce solo a MA e prezzo
# correnti.
# ---------------------------------------------------------------------
def strategy_regime_pyramid(df, threshold_series, atr, regime_ma_period=100,
                              entry_period=15, atr_stop_mult=2.5,
                              pyramid_fraction=0.30, max_pyramids=4):
    ma_regime = df['Close'].rolling(regime_ma_period).mean()
    donch_upper, _ = compute_donchian(df, period=entry_period)

    pf = Portfolio(100.0)
    in_position = False
    trailing_stop = None
    last_action_price = df['Close'].iloc[0]
    n_pyramids = 0

    prices = df['Close'].to_numpy()
    ths = threshold_series.to_numpy()
    upps = donch_upper.to_numpy()
    atrs = atr.to_numpy()
    mas = ma_regime.to_numpy()
    n = len(prices)
    equity_curve = np.empty(n)

    for i in range(n):
        price = prices[i]
        th = ths[i]
        a = atrs[i]
        upper = upps[i]
        ma = mas[i]
        if np.isnan(th) or np.isnan(upper) or np.isnan(a) or np.isnan(ma):
            equity_curve[i] = pf.equity(price)
            continue

        bull_regime = price > ma
        moved_enough = abs(price - last_action_price) >= th

        if bull_regime:
            # Entra o aggiunge posizione (piramida) su ogni nuovo breakout
            if price >= upper and moved_enough and pf.cash > 1 and n_pyramids < max_pyramids:
                pf.buy(price, pyramid_fraction)
                if not in_position:
                    in_position = True
                    trailing_stop = price - atr_stop_mult * a
                n_pyramids += 1
                last_action_price = price
            # aggiorna sempre il trailing stop verso l'alto se in posizione
            if in_position:
                new_stop = price - atr_stop_mult * a
                if new_stop > trailing_stop:
                    trailing_stop = new_stop
                if price <= trailing_stop and pf.eth * price > 1:
                    pf.sell(price, 1.0)
                    in_position = False
                    n_pyramids = 0
                    last_action_price = price
        else:
            # regime bear: esce SUBITO e integralmente, protezione capitale
            if in_position and pf.eth * price > 1:
                pf.sell(price, 1.0)
                in_position = False
                n_pyramids = 0
                last_action_price = price

        equity_curve[i] = pf.equity(price)
    pf.equity_curve = equity_curve
    return pf

# ---------------------------------------------------------------------
# STRATEGIA 4: POSITION SIZING DINAMICO (volatility-based)
# Simile al grid, ma la frazione di capitale investita per trade si
# riduce quando la volatilità (ATR%) è alta, per rispettare il vincolo
# di rischio (max drawdown 50%).
# ---------------------------------------------------------------------
def strategy_vol_sizing(df, threshold_series, atr, base_fraction=0.25):
    pf = Portfolio(100.0)
    ref_price = df['Close'].iloc[0]
    atr_pct = (atr / df['Close']).clip(lower=0.001)
    median_atr_pct = atr_pct.median()
    for i, row in df.iterrows():
        price = row['Close']
        th = threshold_series.iloc[i]
        if pd.isna(th) or th <= 0 or pd.isna(atr_pct.iloc[i]):
            pf.record(price)
            continue
        # scala la size inversamente alla volatilità relativa
        vol_ratio = median_atr_pct / atr_pct.iloc[i]
        vol_ratio = np.clip(vol_ratio, 0.3, 1.5)
        frac = base_fraction * vol_ratio
        frac = min(frac, 0.5)

        if price <= ref_price - th and pf.cash > 1:
            pf.buy(price, frac)
            ref_price = price
        elif price >= ref_price + th and pf.eth * price > 1:
            pf.sell(price, frac)
            ref_price = price
        pf.record(price)
    return pf
