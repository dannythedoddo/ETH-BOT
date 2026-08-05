"""Strategia Regime-Adaptive Pyramid, versione "live": valuta un solo
istante alla volta (l'ultima candela chiusa) invece di iterare su uno
storico, ma la logica è IDENTICA a quella validata nel backtest
(vedi backtest/strategies.py::strategy_regime_pyramid).

Regime "acceso" (prezzo sopra la media lunga) -> entra/piramida sui
breakout, trailing stop ATR.
Regime "spento" (prezzo sotto la media lunga) -> esce subito e
integralmente, resta in liquidità.

Nessuna previsione: ogni decisione usa solo prezzo e indicatori
dell'istante presente.
"""
import logging
import pandas as pd

import config
from indicators import compute_atr, compute_donchian_upper, compute_regime_ma

log = logging.getLogger("eth_bot.strategy")


def evaluate(df, portfolio):
    """Valuta l'ultima candela e applica al massimo un'azione (buy o sell).
    `df` deve contenere almeno REGIME_MA_PERIOD candele di storico.
    `portfolio` è un'istanza di PaperPortfolio (o equivalente live).
    Ritorna il portfolio aggiornato.
    """
    if len(df) < config.REGIME_MA_PERIOD + 5:
        log.warning(f"Storico insufficiente ({len(df)} candele, "
                    f"servono almeno {config.REGIME_MA_PERIOD + 5}). Skip.")
        return portfolio

    atr = compute_atr(df, config.ATR_PERIOD)
    donch_upper = compute_donchian_upper(df, config.ENTRY_DONCHIAN_PERIOD)
    regime_ma = compute_regime_ma(df, config.REGIME_MA_PERIOD)

    price = float(df["Close"].iloc[-1])
    a = float(atr.iloc[-1])
    upper = float(donch_upper.iloc[-1])
    ma = float(regime_ma.iloc[-1])

    if pd.isna(a) or pd.isna(upper) or pd.isna(ma):
        log.info("Indicatori non ancora disponibili (NaN), skip.")
        return portfolio

    s = portfolio.state
    last_action_price = s["last_action_price"] if s["last_action_price"] else price
    threshold = price * config.BREAKOUT_THRESHOLD_PCT
    moved_enough = abs(price - last_action_price) >= threshold
    bull_regime = price > ma

    # --- kill switch di rischio ---
    equity = portfolio.equity(price)
    s["peak_equity"] = max(s["peak_equity"], equity)
    drawdown = (equity - s["peak_equity"]) / s["peak_equity"]
    if abs(drawdown) >= config.MAX_DRAWDOWN_KILL_SWITCH:
        log.warning(f"KILL SWITCH: drawdown {drawdown:.1%} oltre il limite "
                    f"{config.MAX_DRAWDOWN_KILL_SWITCH:.0%}. Bot in pausa.")
        return portfolio

    if bull_regime:
        # entra o piramida su nuovo breakout
        if (price >= upper and moved_enough and s["cash"] > 1
                and s["n_pyramids"] < config.MAX_PYRAMIDS):
            reason = f"breakout regime-bull (prezzo {price:.2f} >= canale {upper:.2f})"
            if portfolio.buy(price, config.PYRAMID_FRACTION, reason=reason):
                if not s["in_position"]:
                    s["in_position"] = True
                    s["trailing_stop"] = price - config.ATR_STOP_MULTIPLIER * a
                s["n_pyramids"] += 1
                s["last_action_price"] = price

        # aggiorna trailing stop e verifica uscita
        if s["in_position"]:
            new_stop = price - config.ATR_STOP_MULTIPLIER * a
            if s["trailing_stop"] is None or new_stop > s["trailing_stop"]:
                s["trailing_stop"] = new_stop
            if price <= s["trailing_stop"] and s["eth"] * price > 1:
                reason = f"trailing stop colpito ({price:.2f} <= {s['trailing_stop']:.2f})"
                if portfolio.sell(price, 1.0, reason=reason):
                    s["in_position"] = False
                    s["n_pyramids"] = 0
                    s["last_action_price"] = price
    else:
        # regime bear: uscita immediata e integrale
        if s["in_position"] and s["eth"] * price > 1:
            reason = f"regime bear (prezzo {price:.2f} sotto MA {ma:.2f}), protezione capitale"
            if portfolio.sell(price, 1.0, reason=reason):
                s["in_position"] = False
                s["n_pyramids"] = 0
                s["last_action_price"] = price

    log.info(f"Prezzo: {price:.2f} | Regime: {'BULL' if bull_regime else 'BEAR'} | "
             f"Equity: {equity:.2f}€ | Drawdown: {drawdown:.1%} | "
             f"In posizione: {s['in_position']} (piramidi: {s['n_pyramids']}) | "
             f"Trade totali: {s['trades_executed']}")

    return portfolio
