"""Recupero prezzi di mercato reali da API pubblica (nessuna API key
richiesta). Usato sia in paper trading che in modalità live: il bot
osserva sempre il mercato reale, cambia solo se gli ordini sono
simulati o eseguiti davvero on-chain.
"""
import requests
import pandas as pd
import logging

log = logging.getLogger("eth_bot.data_feed")

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"


def fetch_recent_candles(symbol="ETHUSDT", interval="15m", limit=2000):
    """Scarica le ultime `limit` candele OHLCV. Binance limita a 1000
    per chiamata, quindi paginiamo se serve più storico."""
    all_rows = []
    remaining = limit
    end_time = None

    while remaining > 0:
        batch = min(remaining, 1000)
        params = {"symbol": symbol, "interval": interval, "limit": batch}
        if end_time:
            params["endTime"] = end_time
        r = requests.get(BINANCE_KLINES_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        all_rows = data + all_rows
        end_time = data[0][0] - 1  # candela precedente alla prima ricevuta
        remaining -= len(data)
        if len(data) < batch:
            break  # non ci sono più dati storici disponibili

    df = pd.DataFrame(all_rows, columns=[
        "open_time", "Open", "High", "Low", "Close", "Volume",
        "close_time", "qav", "trades", "tbbav", "tbqav", "ignore"
    ])
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = df[col].astype(float)
    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)
    return df[["timestamp", "Open", "High", "Low", "Close", "Volume"]]


def get_current_price(df):
    """Ultimo prezzo di chiusura disponibile."""
    return float(df["Close"].iloc[-1])
