"""
Bot ETH — Regime-Adaptive Pyramid Strategy
============================================
Entry point principale. In modalità paper trading (default) simula un
portafoglio virtuale sui prezzi REALI di mercato, senza toccare wallet
o fondi veri. Utile per validare la strategia "sul presente" prima di
passare a capitale reale.

Uso:
    python main.py                # avvia il loop continuo (ogni 15 min)
    python main.py --once         # esegue una sola valutazione e esce
    python main.py --status       # mostra lo stato attuale del portafoglio ed esce
"""
import sys
import time
import logging
import argparse

import config
import data_feed
import history_store
import strategy
from paper_trader import PaperPortfolio

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(config.LOG_FILE), logging.StreamHandler()]
)
log = logging.getLogger("eth_bot.main")


def print_status(portfolio, price):
    s = portfolio.state
    equity = portfolio.equity(price)
    ret_pct = (equity / config.INITIAL_CAPITAL_USD - 1) * 100
    print("=" * 60)
    print(f"  Capitale iniziale virtuale : {config.INITIAL_CAPITAL_USD:.2f}€")
    print(f"  Prezzo ETH attuale         : {price:.2f}€")
    print(f"  Cash                       : {s['cash']:.2f}€")
    print(f"  ETH detenuto               : {s['eth']:.6f} ({s['eth']*price:.2f}€)")
    print(f"  Equity totale              : {equity:.2f}€")
    print(f"  Rendimento                 : {ret_pct:+.2f}%")
    print(f"  In posizione               : {s['in_position']} (piramidi: {s['n_pyramids']})")
    print(f"  Trade eseguiti finora      : {s['trades_executed']}")
    print(f"  Picco equity storico       : {s['peak_equity']:.2f}€")
    print("=" * 60)


def run_once():
    log.info("Carico lo storico persistente e scarico le candele più recenti...")
    old_history = history_store.load_history()
    new_candles = data_feed.fetch_latest_candles(
        pair=config.KRAKEN_PAIR,
        interval=config.CANDLE_INTERVAL
    )
    df = history_store.merge_and_save(old_history, new_candles)

    if len(df) < config.REGIME_MA_PERIOD + 5:
        log.warning(
            f"Storico ancora insufficiente: {len(df)} candele disponibili, "
            f"servono almeno {config.REGIME_MA_PERIOD + 5}. "
            f"Il bot accumulerà storico nei prossimi run (circa "
            f"{(config.REGIME_MA_PERIOD + 5 - len(df)) * 15 / 60:.0f} ore mancanti "
            f"se eseguito ogni 15 minuti). Nessuna azione di trading in questo run."
        )

    log.info(f"Candele totali disponibili: {len(df)}, ultima: {df['timestamp'].iloc[-1]}")

    portfolio = PaperPortfolio()
    portfolio = strategy.evaluate(df, portfolio)
    portfolio.save()

    price = data_feed.get_current_price(df)
    portfolio.snapshot(price)  # aggiorna il foglio "Andamento" dell'Excel ad ogni run
    print_status(portfolio, price)
    return portfolio, price


def run_loop():
    if not config.PAPER_TRADING:
        log.warning("PAPER_TRADING è False: il bot eseguirebbe operazioni REALI. "
                    "Questo script di esempio non implementa l'esecuzione live "
                    "on-chain by default — va completata prima dell'uso reale.")
        sys.exit(1)

    log.info("=== Bot avviato in modalità PAPER TRADING (fondi virtuali) ===")
    log.info(f"Strategia: Regime-Adaptive Pyramid | Capitale virtuale: "
             f"{config.INITIAL_CAPITAL_USD}€ | Check ogni {config.CHECK_INTERVAL_SECONDS}s")

    while True:
        try:
            run_once()
        except Exception as e:
            log.error(f"Errore nel ciclo: {e}", exc_info=True)
        time.sleep(config.CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ETH Regime-Adaptive Pyramid Bot")
    parser.add_argument("--once", action="store_true", help="Esegue una sola valutazione ed esce")
    parser.add_argument("--status", action="store_true", help="Mostra lo stato attuale ed esce")
    args = parser.parse_args()

    if args.status:
        df = history_store.load_history()
        if len(df) == 0:
            print("Nessuno storico ancora disponibile. Esegui prima 'python main.py --once'.")
            sys.exit(0)
        price = data_feed.get_current_price(df)
        portfolio = PaperPortfolio()
        print_status(portfolio, price)
    elif args.once:
        run_once()
    else:
        run_loop()
