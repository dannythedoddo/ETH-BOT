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
