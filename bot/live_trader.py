"""Esecuzione LIVE on-chain (Uniswap V3 su Arbitrum). Espone la stessa
interfaccia di `PaperPortfolio` (buy/sell/equity/save/snapshot) così
`strategy.py` funziona identico in paper trading e in live, senza
modifiche alla logica della strategia.

*** LEGGI PRIMA DI USARE CON FONDI VERI ***
- Verifica SEMPRE gli indirizzi dei contratti in config.py contro le
  pagine ufficiali di Uniswap/Arbiscan prima del primo utilizzo reale.
- Testa su una testnet (Arbitrum Sepolia) prima di mainnet.
- Usa un wallet dedicato, con solo il capitale che vuoi rischiare.
- La chiave privata va SEMPRE e SOLO in una variabile d'ambiente
  (BOT_PRIVATE_KEY), mai scritta nel codice o in un file committato.
"""
import json
import time
import logging
from datetime import datetime, timezone

from web3 import Web3
from eth_account import Account

import config
import excel_log

log = logging.getLogger("eth_bot.live")


ERC20_ABI = json.loads('''[
  {"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf",
   "outputs":[{"name":"balance","type":"uint256"}],"type":"function"},
  {"constant":true,"inputs":[{"name":"_owner","type":"address"},{"name":"_spender","type":"address"}],
   "name":"allowance","outputs":[{"name":"","type":"uint256"}],"type":"function"},
  {"constant":false,"inputs":[{"name":"_spender","type":"address"},{"name":"_value","type":"uint256"}],
   "name":"approve","outputs":[{"name":"","type":"bool"}],"type":"function"},
  {"constant":true,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"}
]''')

UNISWAP_ROUTER_ABI = json.loads('''[
  {"inputs":[{"components":[
      {"internalType":"address","name":"tokenIn","type":"address"},
      {"internalType":"address","name":"tokenOut","type":"address"},
      {"internalType":"uint24","name":"fee","type":"uint24"},
      {"internalType":"address","name":"recipient","type":"address"},
      {"internalType":"uint256","name":"deadline","type":"uint256"},
      {"internalType":"uint256","name":"amountIn","type":"uint256"},
      {"internalType":"uint256","name":"amountOutMinimum","type":"uint256"},
      {"internalType":"uint160","name":"sqrtPriceLimitX96","type":"uint160"}],
      "internalType":"struct ISwapRouter.ExactInputSingleParams","name":"params","type":"tuple"}],
   "name":"exactInputSingle","outputs":[{"internalType":"uint256","name":"amountOut","type":"uint256"}],
   "stateMutability":"payable","type":"function"}
]''')

QUOTER_V2_ABI = json.loads('''[
  {"inputs":[{"components":[
      {"internalType":"address","name":"tokenIn","type":"address"},
      {"internalType":"address","name":"tokenOut","type":"address"},
      {"internalType":"uint256","name":"amountIn","type":"uint256"},
      {"internalType":"uint24","name":"fee","type":"uint24"},
      {"internalType":"uint160","name":"sqrtPriceLimitX96","type":"uint160"}],
      "internalType":"struct IQuoterV2.QuoteExactInputSingleParams","name":"params","type":"tuple"}],
   "name":"quoteExactInputSingle",
   "outputs":[
      {"internalType":"uint256","name":"amountOut","type":"uint256"},
      {"internalType":"uint160","name":"sqrtPriceX96After","type":"uint160"},
      {"internalType":"uint32","name":"initializedTicksCrossed","type":"uint32"},
      {"internalType":"uint256","name":"gasEstimate","type":"uint256"}],
   "stateMutability":"nonpayable","type":"function"}
]''')


def _require_live_confirmation():
    """Gate di sicurezza aggiuntivo, separato da PAPER_TRADING: bisogna
    impostare ESPLICITAMENTE questa variabile d'ambiente per evitare che
    un errore di configurazione porti a trading reale non voluto."""
    import os
    confirm = os.environ.get("CONFIRM_LIVE_TRADING")
    if confirm != "YES-I-UNDERSTAND-THE-RISKS":
        raise RuntimeError(
            "Esecuzione LIVE richiede la variabile d'ambiente "
            "CONFIRM_LIVE_TRADING='YES-I-UNDERSTAND-THE-RISKS' impostata "
            "esplicitamente, oltre a PAPER_TRADING=False in config.py. "
            "Questo doppio controllo esiste per evitare trading reale "
            "accidentale. Se non sei pronto, non impostarla."
        )


class LivePortfolio:
    def __init__(self, state_file=None):
        _require_live_confirmation()

        self.w3 = Web3(Web3.HTTPProvider(config.RPC_URL))
        if not self.w3.is_connected():
            raise ConnectionError(f"Impossibile connettersi a {config.RPC_URL}")

        self.account = Account.from_key(config.PRIVATE_KEY)
        log.warning(f"=== MODALITA' LIVE ATTIVA === Wallet: {self.account.address}")

        self.usdc = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.USDC_ADDRESS), abi=ERC20_ABI)
        self.weth = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.WETH_ADDRESS), abi=ERC20_ABI)
        self.router = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.UNISWAP_V3_ROUTER), abi=UNISWAP_ROUTER_ABI)
        self.quoter = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.UNISWAP_V3_QUOTER), abi=QUOTER_V2_ABI)

        self.usdc_decimals = self.usdc.functions.decimals().call()
        self.weth_decimals = self.weth.functions.decimals().call()

        self.state_file = state_file or "live_state.json"
        self.state = self._load_or_init_state()
        self._refresh_balances()

    # -------------------------------------------------------------
    # STATO (solo bookkeeping della strategia: trailing stop, ecc.
    # I saldi cash/eth vengono sempre letti dalla blockchain, mai
    # tenuti solo in memoria, per evitare disallineamenti)
    # -------------------------------------------------------------
    def _load_or_init_state(self):
        import os
        if os.path.exists(self.state_file):
            with open(self.state_file) as f:
                return json.load(f)
        return {
            "in_position": False,
            "trailing_stop": None,
            "last_action_price": None,
            "n_pyramids": 0,
            "peak_equity": None,  # inizializzato al primo refresh saldi
            "trades_executed": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def save(self):
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)

    def _refresh_balances(self):
        usdc_raw = self.usdc.functions.balanceOf(self.account.address).call()
        weth_raw = self.weth.functions.balanceOf(self.account.address).call()
        self.state["cash"] = usdc_raw / (10 ** self.usdc_decimals)
        self.state["eth"] = weth_raw / (10 ** self.weth_decimals)
        if self.state["peak_equity"] is None:
            # inizializza il picco al valore attuale al primissimo avvio
            self.state["peak_equity"] = self.state["cash"]

    def equity(self, price):
        return self.state["cash"] + self.state["eth"] * price

    # -------------------------------------------------------------
    # QUOTAZIONE E SLIPPAGE
    # -------------------------------------------------------------
    def _get_quote(self, token_in, token_out, amount_in_raw):
        params = (
            Web3.to_checksum_address(token_in),
            Web3.to_checksum_address(token_out),
            amount_in_raw,
            config.POOL_FEE_TIER,
            0,
        )
        result = self.quoter.functions.quoteExactInputSingle(params).call()
        return result[0]  # amountOut atteso

    def _ensure_approval(self, token_contract, spender, amount_raw):
        allowance = token_contract.functions.allowance(
            self.account.address, spender).call()
        if allowance >= amount_raw:
            return
        log.info(f"Approvo {spender} a spendere il token {token_contract.address}...")
        tx = token_contract.functions.approve(spender, 2**256 - 1).build_transaction({
            "from": self.account.address,
            "nonce": self.w3.eth.get_transaction_count(self.account.address),
            "gas": 100000,
            "maxFeePerGas": self.w3.eth.gas_price * 2,
            "maxPriorityFeePerGas": self.w3.to_wei(0.01, "gwei"),
            "chainId": config.CHAIN_ID,
        })
        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt.status != 1:
            raise RuntimeError(f"Approve fallita! tx: {tx_hash.hex()}")
        log.info(f"Approve confermata: {tx_hash.hex()}")

    # -------------------------------------------------------------
    # ESECUZIONE SWAP
    # -------------------------------------------------------------
    def _execute_swap(self, token_in, token_out, amount_in_raw, min_amount_out_raw):
        deadline = int(time.time()) + 300
        params = (
            Web3.to_checksum_address(token_in),
            Web3.to_checksum_address(token_out),
            config.POOL_FEE_TIER,
            self.account.address,
            deadline,
            amount_in_raw,
            min_amount_out_raw,
            0,
        )
        tx = self.router.functions.exactInputSingle(params).build_transaction({
            "from": self.account.address,
            "nonce": self.w3.eth.get_transaction_count(self.account.address),
            "gas": 350000,
            "maxFeePerGas": self.w3.eth.gas_price * 2,
            "maxPriorityFeePerGas": self.w3.to_wei(0.01, "gwei"),
            "chainId": config.CHAIN_ID,
        })
        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        log.info(f"Swap inviato: {tx_hash.hex()}")
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        if receipt.status != 1:
            raise RuntimeError(f"Swap fallito! tx: {tx_hash.hex()}")
        return tx_hash.hex()

    def buy(self, price, fraction, reason=""):
        """Compra WETH spendendo `fraction` del cash USDC disponibile."""
        spend_usd = self.state["cash"] * fraction
        if spend_usd < 1:
            return False

        amount_in_raw = int(spend_usd * (10 ** self.usdc_decimals))
        expected_out_raw = self._get_quote(config.USDC_ADDRESS, config.WETH_ADDRESS, amount_in_raw)
        min_out_raw = int(expected_out_raw * (1 - config.MAX_SLIPPAGE_PCT))

        self._ensure_approval(self.usdc, self.router.address, amount_in_raw)
        tx_hash = self._execute_swap(config.USDC_ADDRESS, config.WETH_ADDRESS,
                                       amount_in_raw, min_out_raw)

        self._refresh_balances()
        self.state["trades_executed"] += 1
        self._log_trade("BUY", price, spend_usd, tx_hash, reason)
        return True

    def sell(self, price, fraction, reason=""):
        """Vende `fraction` del WETH detenuto per USDC."""
        amount_eth = self.state["eth"] * fraction
        if amount_eth * price < 1:
            return False

        amount_in_raw = int(amount_eth * (10 ** self.weth_decimals))
        expected_out_raw = self._get_quote(config.WETH_ADDRESS, config.USDC_ADDRESS, amount_in_raw)
        min_out_raw = int(expected_out_raw * (1 - config.MAX_SLIPPAGE_PCT))

        self._ensure_approval(self.weth, self.router.address, amount_in_raw)
        tx_hash = self._execute_swap(config.WETH_ADDRESS, config.USDC_ADDRESS,
                                       amount_in_raw, min_out_raw)

        self._refresh_balances()
        self.state["trades_executed"] += 1
        self._log_trade("SELL", price, amount_eth * price, tx_hash, reason)
        return True

    def _log_trade(self, side, market_price, notional_usd, tx_hash, reason):
        equity_after = self.equity(market_price)
        log.info(f"{side} eseguito on-chain @ ~{market_price:.2f} | "
                 f"notional≈{notional_usd:.2f}$ | tx: {tx_hash} | motivo: {reason}")
        excel_log.append_trade(
            config.EXCEL_LOG_FILE, side, market_price, market_price, notional_usd,
            self.state["eth"], 0.0,  # fee reale già inclusa nello swap, non separabile facilmente
            f"{reason} | tx:{tx_hash}", self.state["cash"], self.state["eth"],
            equity_after, config.INITIAL_CAPITAL_USD
        )

    def snapshot(self, price):
        self._refresh_balances()
        equity = self.equity(price)
        self.state["peak_equity"] = max(self.state["peak_equity"], equity)
        drawdown = (equity - self.state["peak_equity"]) / self.state["peak_equity"]
        excel_log.append_snapshot(
            config.EXCEL_LOG_FILE, price, self.state["cash"], self.state["eth"], equity,
            config.INITIAL_CAPITAL_USD, drawdown, self.state["in_position"],
            self.state["n_pyramids"], self.state["trades_executed"]
        )
