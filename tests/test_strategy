"""Test di sanità per la strategia e il portafoglio paper trading.
Esegui con: python -m pytest tests/
"""
import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bot"))

import config
from paper_trader import PaperPortfolio
from indicators import compute_atr, compute_donchian_upper, compute_regime_ma


def make_fake_candles(n=2000, start_price=2000.0, trend=0.0002, seed=42):
    """Genera candele sintetiche con un trend leggero, per test rapidi
    senza dipendere dalla rete."""
    rng = np.random.default_rng(seed)
    returns = rng.normal(trend, 0.01, n)
    prices = start_price * np.cumprod(1 + returns)
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC"),
        "Open": prices,
        "High": prices * (1 + np.abs(rng.normal(0, 0.003, n))),
        "Low": prices * (1 - np.abs(rng.normal(0, 0.003, n))),
        "Close": prices,
        "Volume": rng.uniform(100, 1000, n),
    })
    return df


def test_indicators_no_crash():
    df = make_fake_candles()
    atr = compute_atr(df)
    donch = compute_donchian_upper(df)
    ma = compute_regime_ma(df, period=500)
    assert len(atr) == len(df)
    assert not atr.iloc[-1] != atr.iloc[-1]  # non NaN sull'ultimo valore
    assert not donch.iloc[-1] != donch.iloc[-1]
    assert not ma.iloc[-1] != ma.iloc[-1]


def test_paper_portfolio_buy_sell(tmp_path):
    state_file = str(tmp_path / "test_state.json")
    pf = PaperPortfolio(state_file=state_file)
    assert pf.state["cash"] == config.INITIAL_CAPITAL_USD

    ok = pf.buy(price=2000.0, fraction=0.5, reason="test")
    assert ok
    assert pf.state["eth"] > 0
    assert pf.state["cash"] < config.INITIAL_CAPITAL_USD

    eth_before = pf.state["eth"]
    ok = pf.sell(price=2100.0, fraction=1.0, reason="test exit")
    assert ok
    assert pf.state["eth"] < eth_before

    # lo stato deve persistere su file
    pf.save()
    assert os.path.exists(state_file)


def test_equity_never_negative():
    df = make_fake_candles(n=3000, trend=-0.001)  # trend fortemente ribassista
    import strategy
    from paper_trader import PaperPortfolio
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        pf = PaperPortfolio(state_file=os.path.join(d, "state.json"))
        for i in range(config.REGIME_MA_PERIOD + 10, len(df), 20):
            sub = df.iloc[:i]
            pf = strategy.evaluate(sub, pf)
            price = sub["Close"].iloc[-1]
            assert pf.equity(price) >= 0, "L'equity non deve mai andare negativa"
