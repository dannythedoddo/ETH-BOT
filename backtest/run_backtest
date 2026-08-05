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

"""
Backtest engine per bot trading ETH.
Testa 3 tipi di soglia (fissa €, dinamica %, ATR-based) x 4 strategie adattive.
Capitale iniziale: 100€. Reinvestimento completo (compounding).
Commissioni realistiche incluse (Binance spot: 0.1% taker per lato, tipico anche per bot retail).
"""
import pandas as pd
import numpy as np

FEE_RATE = 0.001  # 0.1% per operazione (standard exchange, es. Binance/Kraken)
SLIPPAGE = 0.0005  # 0.05% slippage stimato su timeframe 15m con capitale piccolo
INITIAL_CAPITAL = 100.0
MAX_DRAWDOWN_LIMIT = 0.50

def load_data(path):
    df = pd.read_csv(path, parse_dates=['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    return df

def compute_atr(df, period=14):
    high, low, close = df['High'], df['Low'], df['Close']
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return atr

def compute_bollinger(df, period=20, num_std=2):
    ma = df['Close'].rolling(period).mean()
    std = df['Close'].rolling(period).std()
    upper = ma + num_std * std
    lower = ma - num_std * std
    return ma, upper, lower

def compute_donchian(df, period=20):
    upper = df['High'].rolling(period).max()
    lower = df['Low'].rolling(period).min()
    return upper, lower

def max_drawdown(equity_curve):
    peak = np.maximum.accumulate(equity_curve)
    dd = (equity_curve - peak) / peak
    return dd.min()  # negativo

class Portfolio:
    def __init__(self, initial_capital):
        self.cash = initial_capital
        self.eth = 0.0
        self.trades = 0
        self.equity_curve = []

    def buy(self, price, fraction):
        """Compra usando `fraction` del cash disponibile."""
        spend = self.cash * fraction
        if spend < 1:  # evita micro-trade inutili sotto 1€
            return
        exec_price = price * (1 + SLIPPAGE)
        fee = spend * FEE_RATE
        eth_bought = (spend - fee) / exec_price
        self.eth += eth_bought
        self.cash -= spend
        self.trades += 1

    def sell(self, price, fraction):
        """Vende `fraction` dell'ETH detenuto."""
        amount = self.eth * fraction
        if amount * price < 1:
            return
        exec_price = price * (1 - SLIPPAGE)
        proceeds = amount * exec_price
        fee = proceeds * FEE_RATE
        self.cash += (proceeds - fee)
        self.eth -= amount
        self.trades += 1

    def equity(self, price):
        return self.cash + self.eth * price

    def record(self, price):
        self.equity_curve.append(self.equity(price))

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
