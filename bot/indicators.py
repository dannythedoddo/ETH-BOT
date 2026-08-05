"""Indicatori tecnici - identici a quelli usati nel backtest, per
garantire che il comportamento live rispecchi esattamente i risultati
storici testati.
"""
import pandas as pd


def compute_atr(df, period=14):
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def compute_donchian_upper(df, period=20):
    return df["High"].rolling(period).max()


def compute_regime_ma(df, period=1500):
    return df["Close"].rolling(period).mean()
