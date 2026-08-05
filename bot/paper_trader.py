"""Portafoglio virtuale per il paper trading. Nessun fondo reale, nessun
wallet coinvolto — simula fedelmente commissioni e slippage per dare
un'idea realistica di come si comporterebbe il bot dal vivo.

Lo stato viene salvato su file JSON per sopravvivere a riavvii dello
script (importante se il bot gira per settimane).
"""
import json
import csv
import os
import logging
from datetime import datetime, timezone

import config
import excel_log

log = logging.getLogger("eth_bot.paper")


class PaperPortfolio:
    def __init__(self, state_file=config.STATE_FILE):
        self.state_file = state_file
        self.state = self._load_or_init()

    def _load_or_init(self):
        if os.path.exists(self.state_file):
            with open(self.state_file) as f:
                state = json.load(f)
            log.info(f"Stato caricato da {self.state_file}: "
                     f"cash={state['cash']:.2f} eth={state['eth']:.6f}")
            return state
        log.info(f"Nessuno stato precedente trovato, inizializzo con "
                 f"{config.INITIAL_CAPITAL_USD}€ virtuali")
        return {
            "cash": config.INITIAL_CAPITAL_USD,
            "eth": 0.0,
            "in_position": False,
            "trailing_stop": None,
            "last_action_price": None,
            "n_pyramids": 0,
            "peak_equity": config.INITIAL_CAPITAL_USD,
            "trades_executed": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def save(self):
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)

    def equity(self, price):
        return self.state["cash"] + self.state["eth"] * price

    def buy(self, price, fraction, reason=""):
        spend = self.state["cash"] * fraction
        if spend < 1:
            return False
        exec_price = price * (1 + config.SIMULATED_SLIPPAGE)
        fee = spend * config.SIMULATED_FEE_RATE
        eth_bought = (spend - fee) / exec_price
        self.state["eth"] += eth_bought
        self.state["cash"] -= spend
        self.state["trades_executed"] += 1
        self._log_trade("BUY", price, exec_price, spend, eth_bought, fee, reason)
        return True

    def sell(self, price, fraction, reason=""):
        amount = self.state["eth"] * fraction
        if amount * price < 1:
            return False
        exec_price = price * (1 - config.SIMULATED_SLIPPAGE)
        proceeds = amount * exec_price
        fee = proceeds * config.SIMULATED_FEE_RATE
        self.state["cash"] += (proceeds - fee)
        self.state["eth"] -= amount
        self.state["trades_executed"] += 1
        self._log_trade("SELL", price, exec_price, proceeds, amount, fee, reason)
        return True

    def _log_trade(self, side, price, exec_price, notional, amount_eth, fee, reason):
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "side": side,
            "market_price": round(price, 2),
            "exec_price": round(exec_price, 2),
            "notional_usd": round(notional, 2),
            "amount_eth": round(amount_eth, 6),
            "fee_usd": round(fee, 4),
            "reason": reason,
            "cash_after": round(self.state["cash"], 2),
            "eth_after": round(self.state["eth"], 6),
        }
        file_exists = os.path.exists(config.TRADE_LOG_FILE)
        with open(config.TRADE_LOG_FILE, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
        log.info(f"{side} @ {exec_price:.2f} | notional={notional:.2f}€ | "
                 f"fee={fee:.4f}€ | motivo: {reason}")

        # aggiorna anche il file Excel (una riga per trade, foglio "Trades")
        equity_after = self.state["cash"] + self.state["eth"] * price
        excel_log.append_trade(
            config.EXCEL_LOG_FILE, side, price, exec_price, notional,
            amount_eth, fee, reason, self.state["cash"], self.state["eth"],
            equity_after, config.INITIAL_CAPITAL_USD
        )

    def snapshot(self, price):
        """Registra un punto nel foglio 'Andamento' dell'Excel, anche se
        in questo ciclo non è avvenuto nessun trade. Chiamato ad ogni
        esecuzione del bot per tracciare l'andamento nel tempo."""
        s = self.state
        equity = self.equity(price)
        drawdown = (equity - s["peak_equity"]) / s["peak_equity"] if s["peak_equity"] else 0.0
        excel_log.append_snapshot(
            config.EXCEL_LOG_FILE, price, s["cash"], s["eth"], equity,
            config.INITIAL_CAPITAL_USD, drawdown, s["in_position"],
            s["n_pyramids"], s["trades_executed"]
        )
