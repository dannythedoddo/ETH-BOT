"""Gestisce `price_history.csv`: lo storico delle candele necessario a
calcolare gli indicatori (in particolare la media di regime a 1500
periodi). Il file viene committato nel repository dal workflow GitHub
Actions, quindi cresce nel tempo run dopo run senza dover riscaricare
tutto lo storico ad ogni esecuzione.
"""
import os
import logging
import pandas as pd

import config

log = logging.getLogger("eth_bot.history_store")

# Margine di sicurezza oltre il minimo strettamente necessario
# (REGIME_MA_PERIOD), per avere sempre indicatori ben definiti.
MAX_HISTORY_CANDLES = config.REGIME_MA_PERIOD + 500


def load_history(path=config.PRICE_HISTORY_FILE):
    if not os.path.exists(path):
        log.info(f"Nessuno storico precedente trovato in {path}.")
        return pd.DataFrame(columns=["timestamp", "Open", "High", "Low", "Close", "Volume"])
    df = pd.read_csv(path, parse_dates=["timestamp"])
    log.info(f"Storico caricato: {len(df)} candele, da {df['timestamp'].min()} a {df['timestamp'].max()}")
    return df


def merge_and_save(old_df, new_df, path=config.PRICE_HISTORY_FILE):
    """Unisce storico esistente e nuove candele, rimuove duplicati per
    timestamp, tronca alla lunghezza massima necessaria e salva."""
    if len(old_df) == 0:
        combined = new_df.copy()
    else:
        combined = pd.concat([old_df, new_df], ignore_index=True)

    combined["timestamp"] = pd.to_datetime(combined["timestamp"], utc=True)
    combined = combined.drop_duplicates(subset="timestamp").sort_values("timestamp")

    if len(combined) > MAX_HISTORY_CANDLES:
        combined = combined.iloc[-MAX_HISTORY_CANDLES:]

    combined = combined.reset_index(drop=True)
    combined.to_csv(path, index=False)
    log.info(f"Storico aggiornato e salvato: {len(combined)} candele "
             f"(da {combined['timestamp'].min()} a {combined['timestamp'].max()})")
    return combined
