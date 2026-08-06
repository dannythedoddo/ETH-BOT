"""Recupero prezzi di mercato reali. Usa l'API pubblica di Kraken invece
di Binance perché Binance.com blocca esplicitamente le richieste (HTTP 451)
provenienti da IP statunitensi — e i runner di GitHub Actions girano su
infrastruttura Azure negli USA.

Kraken restituisce solo le ~720 candele più recenti per richiesta (limite
dell'endpoint pubblico), quindi per avere lo storico profondo necessario
alla strategia (media di regime a 1500 candele) il bot mantiene un file
CSV persistente (`price_history.csv`, committato nel repo ad ogni run)
che si arricchisce delle nuove candele ad ogni esecuzione — non serve
riscaricare tutto lo storico ogni volta.
"""
import requests
import pandas as pd
import logging

log = logging.getLogger("eth_bot.data_feed")

KRAKEN_OHLC_URL = "https://api.kraken.com/0/public/OHLC"

_INTERVAL_MINUTES = {"15m": 15, "1h": 60, "4h": 240, "1d": 1440}


def fetch_latest_candles(pair="ETHUSD", interval="15m"):
    """Scarica le candele più recenti disponibili da Kraken (fino a ~720).
    Usato per aggiornare lo storico persistente ad ogni run del bot."""
    minutes = _INTERVAL_MINUTES[interval]
    params = {"pair": pair, "interval": minutes}
    r = requests.get(KRAKEN_OHLC_URL, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()

    if data.get("error"):
        raise RuntimeError(f"Errore API Kraken: {data['error']}")

    result = data["result"]
    pair_key = next(k for k in result.keys() if k != "last")
    rows = result[pair_key]

    df = pd.DataFrame(rows, columns=[
        "time", "Open", "High", "Low", "Close", "vwap", "Volume", "count"
    ])
    df["timestamp"] = pd.to_datetime(df["time"], unit="s", utc=True)
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = df[col].astype(float)
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Scarta l'ultima candela: Kraken la include sempre anche se non ancora
    # chiusa/completata, e usarla falserebbe gli indicatori.
    df = df.iloc[:-1]
    return df[["timestamp", "Open", "High", "Low", "Close", "Volume"]]


def get_current_price(df):
    return float(df["Close"].iloc[-1])
