"""Motore di backtest CORRETTO.

Correzione chiave rispetto alla versione precedente: tutti gli indicatori
usati per prendere una decisione sono calcolati sui dati FINO ALLA CANDELA
PRECEDENTE (shift 1). Nella versione precedente il canale Donchian
includeva la candela corrente, il che rendeva la condizione d'ingresso
"Close >= massimo che include il High della candela stessa" — di fatto
un'informazione non disponibile al momento della decisione.
"""
import numpy as np
import pandas as pd

FEE_RATE = 0.001
SLIPPAGE = 0.0005
INITIAL_CAPITAL = 100.0


def load_data(path):
    df = pd.read_csv(path, parse_dates=['timestamp'])
    return df.sort_values('timestamp').reset_index(drop=True)


def compute_atr(df, period=14):
    high, low, close = df['High'], df['Low'], df['Close']
    pc = close.shift(1)
    tr = pd.concat([high - low, (high - pc).abs(), (low - pc).abs()], axis=1).max(axis=1)
    # shift(1): l'ATR usato a t deve basarsi su dati fino a t-1
    return tr.rolling(period).mean().shift(1)


def donchian_upper(df, period):
    """Massimo dei `period` bar PRECEDENTI (esclude la candela corrente)."""
    return df['High'].rolling(period).max().shift(1)


def donchian_lower(df, period):
    return df['Low'].rolling(period).min().shift(1)


def regime_ma(df, period):
    """Media dei `period` close PRECEDENTI."""
    return df['Close'].rolling(period).mean().shift(1)


def max_drawdown(eq):
    peak = np.maximum.accumulate(eq)
    return ((eq - peak) / peak).min()


def cagr(eq, years):
    tot = eq[-1] / INITIAL_CAPITAL
    if tot <= 0:
        return -100.0
    return (tot ** (1 / years) - 1) * 100


class Portfolio:
    def __init__(self, capital=INITIAL_CAPITAL):
        self.cash = capital
        self.eth = 0.0
        self.trades = 0

    def buy(self, price, fraction):
        spend = self.cash * fraction
        if spend < 1:
            return False
        px = price * (1 + SLIPPAGE)
        fee = spend * FEE_RATE
        self.eth += (spend - fee) / px
        self.cash -= spend
        self.trades += 1
        return True

    def sell(self, price, fraction):
        amt = self.eth * fraction
        if amt * price < 1:
            return False
        px = price * (1 - SLIPPAGE)
        proceeds = amt * px
        self.cash += proceeds - proceeds * FEE_RATE
        self.eth -= amt
        self.trades += 1
        return True

    def equity(self, price):
        return self.cash + self.eth * price
