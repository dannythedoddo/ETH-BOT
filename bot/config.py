"""
Configurazione centrale del bot.

MODALITA' PAPER TRADING (default): nessun wallet, nessuna chiave privata,
nessun fondo reale coinvolto. Il bot legge prezzi reali dal mercato e
simula un portafoglio virtuale, utile per validare la strategia "sul
presente" prima di rischiare capitale vero.

Per passare a esecuzione reale (LIVE, on-chain su Arbitrum/Base) vedi
la sezione in fondo — richiede setup aggiuntivo e va attivato
esplicitamente.
"""
import os

# =======================================================================
# MODALITA' DI ESECUZIONE
# =======================================================================
PAPER_TRADING = True   # <-- lascialo True finché non hai validato il bot
                        #     per settimane con fondi virtuali

# =======================================================================
# CAPITALE VIRTUALE (paper trading)
# =======================================================================
INITIAL_CAPITAL_USD = 100.0

# =======================================================================
# STRATEGIA: Regime-Adaptive Pyramid
# Parametri ottimizzati da backtest su 5 anni di dati ETH/USDT 15m
# (2021-2026). Risultato: CAGR +6.5%/anno, Max Drawdown -11.4%,
# positiva in ogni anno solare testato (incluso il crollo 2022).
# =======================================================================
REGIME_MA_PERIOD = 1500      # media mobile di regime, in candele 15m (~15.6 giorni)
ENTRY_DONCHIAN_PERIOD = 25   # canale di breakout per l'entrata/piramidazione
ATR_PERIOD = 14
ATR_STOP_MULTIPLIER = 3.5    # ampiezza trailing stop in multipli di ATR
BREAKOUT_THRESHOLD_PCT = 0.02  # 2% - movimento minimo per confermare un segnale
PYRAMID_FRACTION = 0.90      # % del cash disponibile investito ad ogni breakout
MAX_PYRAMIDS = 10            # numero massimo di aggiunte di posizione per trend

# =======================================================================
# GESTIONE RISCHIO
# =======================================================================
MAX_DRAWDOWN_KILL_SWITCH = 0.50  # oltre questa soglia il bot si ferma (solo vendite)

# =======================================================================
# COSTI SIMULATI (paper trading) - per rendere la simulazione realistica
# =======================================================================
SIMULATED_FEE_RATE = 0.001    # 0.1% - fee tipica DEX/CEX
SIMULATED_SLIPPAGE = 0.0005   # 0.05% - stima slippage su pool liquidi L2

# =======================================================================
# DATI DI MERCATO
# =======================================================================
SYMBOL = "ETHUSDT"
CANDLE_INTERVAL = "15m"
PRICE_HISTORY_LIMIT = 2000   # candele storiche da scaricare a ogni avvio
                              # (deve coprire almeno REGIME_MA_PERIOD)

CHECK_INTERVAL_SECONDS = 900  # 15 minuti, allineato al timeframe strategia

# =======================================================================
# LOGGING / STATO
# =======================================================================
STATE_FILE = "paper_state.json"
LOG_FILE = "bot.log"
TRADE_LOG_FILE = "trades.csv"
EXCEL_LOG_FILE = "trades.xlsx"   # arricchito ad ogni trade + snapshot periodico

# =======================================================================
# ESECUZIONE LIVE (on-chain, Arbitrum) - DISATTIVATA di default
# Da attivare SOLO dopo settimane di validazione in paper trading.
# =======================================================================
if not PAPER_TRADING:
    RPC_URL = os.environ.get("RPC_URL", "")
    PRIVATE_KEY = os.environ.get("BOT_PRIVATE_KEY")  # MAI hardcoded
    if not RPC_URL or not PRIVATE_KEY:
        raise RuntimeError(
            "Modalità LIVE richiede RPC_URL e BOT_PRIVATE_KEY come variabili "
            "d'ambiente. Non impostarle nel codice. Se non sei pronto per il "
            "live trading, lascia PAPER_TRADING = True."
        )
    CHAIN_ID = 42161  # Arbitrum One
    WETH_ADDRESS = "0x82aF49447D8a07e3bd95BD0d56f35241523fBab0"
    USDC_ADDRESS = "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"
    UNISWAP_V3_ROUTER = "0xE592427A0AEce92De3Edee1F18E0157C05861564"
    POOL_FEE_TIER = 500
