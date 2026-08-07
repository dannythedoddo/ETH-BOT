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
# STRATEGIA: Regime Filter + Donchian Breakout + ATR Trailing Stop
# Timeframe 4 ore. Parametri scelti al centro di una zona stabile,
# NON sul picco massimo, per ridurre il rischio di overfitting.
#
# Validazione: ottimizzazione su 2021-2024, verifica su 2024-2026
# (dati mai usati in ottimizzazione). Su 125 configurazioni testate,
# il 74% resta positiva nel periodo di verifica e 10/10 delle migliori
# in ottimizzazione lo restano — segno di robustezza, non di fortuna.
#
# Risultato periodo completo 2021-2026:
#   CAGR +27.2%/anno | Max Drawdown -34.3% | 134 operazioni
#   Positiva in ogni anno solare (2022: +27.4% contro -67.9% del mercato)
# =======================================================================
REGIME_MA_PERIOD = 180       # media mobile di regime, in candele 4h (= 30 giorni)
ENTRY_DONCHIAN_PERIOD = 20   # canale di breakout per l'entrata
ATR_PERIOD = 14
ATR_STOP_MULTIPLIER = 5.0    # ampiezza trailing stop in multipli di ATR
BREAKOUT_THRESHOLD_PCT = 0.02  # 2% - movimento minimo per confermare un segnale
PYRAMID_FRACTION = 1.00      # investe tutto il cash disponibile all'ingresso
MAX_PYRAMIDS = 1             # ingresso singolo (la piramidazione non ha
                              # mostrato valore aggiunto nei test)

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
KRAKEN_PAIR = "ETHUSD"
CANDLE_INTERVAL = "4h"
PRICE_HISTORY_FILE = "price_history.csv"  # storico persistente, cresce ad ogni run

CHECK_INTERVAL_SECONDS = 3600  # 1 ora (il timeframe strategia è 4h;
                                # controllare più spesso non fa danni)

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
