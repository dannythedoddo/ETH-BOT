"""Indicatori tecnici.

IMPORTANTE — correzione applicata: tutti gli indicatori sono calcolati
sui dati fino alla candela PRECEDENTE (shift 1). Nella versione
precedente il canale Donchian includeva la candela corrente, rendendo
la condizione d'ingresso di fatto irrealizzabile (richiedeva che la
candela chiudesse esattamente sul proprio massimo). Questo faceva
scattare il segnale 60 volte meno del previsto e invalidava i risultati
del backtest.
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
    return tr.rolling(period).mean().shift(1)


def compute_donchian_upper(df, period=20):
    """Massimo dei `period` bar PRECEDENTI (esclude la candela corrente)."""
    return df["High"].rolling(period).max().shift(1)


def compute_regime_ma(df, period=180):
    """Media dei `period` close PRECEDENTI."""
    return df["Close"].rolling(period).mean().shift(1)
