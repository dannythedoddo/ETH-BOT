# ETH Regime Trend Bot

Bot di trading per ETH con strategia **non-predittiva e adattiva**: protegge il capitale nei crolli e cattura parte dei rally, reagendo solo al prezzo presente e passato — nessuna previsione, nessun modello di machine learning.

Validato su **5 anni di dati storici reali** (ETH/USDT, candele 4 ore, 2021–2026): `+27.2% CAGR`, `-34.3%` max drawdown, 134 operazioni, positivo in **ogni anno solare** testato incluso il crollo del 2022 (+27.4% mentre il mercato faceva -67.9%).

### Metodo di validazione

I parametri sono stati ottimizzati **solo** sul periodo 2021–2024 e poi verificati sul 2024–2026, dati mai visti durante l'ottimizzazione. Su 125 configurazioni testate, il **74% resta positiva** nel periodo di verifica, e **10 su 10** delle migliori in ottimizzazione lo restano. La configurazione scelta sta al centro di questa zona stabile, non sul picco massimo — un picco isolato sarebbe un segnale di overfitting.

> **Nota storica**: una versione precedente di questo bot conteneva un errore negli indicatori (il canale Donchian includeva la candela corrente, introducendo look-ahead bias). Il risultato apparentemente buono di quella versione era un artefatto del bug, non un vantaggio reale. L'errore è stato corretto e tutti i risultati qui riportati provengono dal motore corretto (`backtest/engine_v2.py`).

## ⚠️ Stato attuale: PAPER TRADING (fondi virtuali)

Questo bot parte in modalità simulazione: legge prezzi **reali** dal mercato ma opera su un portafoglio **virtuale**. Nessun wallet, nessuna chiave privata, nessun fondo reale è coinvolto finché non lo attivi esplicitamente (vedi sezione "Passare al live trading" più sotto).

## Come funziona la strategia

Il bot lavora su candele da **4 ore**. Una media mobile a 180 periodi (= 30 giorni) fa da interruttore di regime:

- **Regime "bull"** (prezzo sopra la media): quando il prezzo rompe il massimo delle 20 candele precedenti (~3 giorni), il bot entra investendo tutto il capitale disponibile. Un trailing stop a 5×ATR segue poi il prezzo verso l'alto.
- **Regime "bear"** (prezzo sotto la media): uscita **immediata e integrale**, il capitale resta in liquidità finché il regime non torna bull.

L'ingresso è singolo: la piramidazione (aggiungere posizione durante il trend) è stata testata e **non ha mostrato valore aggiunto**, quindi è stata rimossa a favore della semplicità.

Tutte le decisioni usano solo dati presenti/passati — è reattiva, non predittiva.

## Fonte dei dati di mercato

Il bot usa l'**API pubblica di Kraken** (nessuna API key richiesta). In precedenza usava Binance, ma Binance.com blocca esplicitamente (HTTP 451) le richieste da IP statunitensi — e i runner di GitHub Actions girano su infrastruttura Azure negli USA, quindi da lì non funzionava.

Il bot mantiene uno **storico persistente** in `bot/price_history.csv`, che si arricchisce delle nuove candele ad ogni esecuzione. Il repository include già un seed di 600 candele da 4 ore (100 giorni), sufficiente a coprire la media di regime a 30 giorni fin dal primo avvio.

## Setup

```bash
git clone <questo-repo>
cd eth-regime-bot
pip install -r requirements.txt
```

## Avvio (paper trading)

```bash
cd bot

# Una singola valutazione (utile per testare che tutto funzioni)
python main.py --once

# Vedi lo stato attuale del portafoglio virtuale
python main.py --status

# Loop continuo (il timeframe della strategia è 4 ore)
python main.py
```

Lo stato del portafoglio virtuale viene salvato in `bot/paper_state.json`, i log in `bot/bot.log`, e ogni trade simulato in `bot/trades.csv` e `bot/trades.xlsx` (con timestamp, prezzo, motivo dell'operazione, commissioni simulate).

## 🤖 Far girare il bot su GitHub (computer spento)

Il repository include un workflow GitHub Actions (`.github/workflows/bot.yml`) che esegue il bot **ogni ora sui server di GitHub**, senza bisogno di tenere il tuo computer acceso. Ad ogni esecuzione, i risultati vengono salvati automaticamente nel repository:

- `bot/trades.xlsx` — **si arricchisce di una riga ogni volta che il bot completa un trade** (foglio "Trades"), più uno snapshot dell'equity ad ogni controllo anche senza trade (foglio "Andamento") — utile per un grafico dell'andamento nel tempo
- `bot/trades.csv` — stesso log in formato CSV
- `bot/paper_state.json` — stato del portafoglio virtuale (persiste tra un'esecuzione e l'altra)
- `bot/price_history.csv` — storico prezzi, cresce ad ogni run
- `bot/bot.log` — log testuale dettagliato

### Setup (una tantum)

1. Pubblica il repository su GitHub (pubblico o privato, funziona in entrambi i casi). **Attenzione**: carica i file dentro il repository, non una cartella che li contiene — dalla home del repo devi vedere direttamente `bot/`, `backtest/`, `.github/`, non una sottocartella `eth-regime-bot/` che le racchiude. Se carichi manualmente da interfaccia web, verifica anche che ogni file `.py` mantenga la sua estensione (a volte va persa nel drag-and-drop).
2. Vai su **Settings → Actions → General**, in fondo alla pagina in "Workflow permissions" seleziona **"Read and write permissions"** e salva — senza questo passaggio il bot non può salvare i risultati nel repo
3. Vai sulla tab **Actions** del repository: dovresti già vedere il workflow "ETH Regime Bot - Paper Trading". Puoi lanciarlo manualmente subito con il pulsante **"Run workflow"** per testarlo, oppure aspettare la prossima esecuzione schedulata (ogni ora)

### Come consultare l'andamento

Scarica `bot/trades.xlsx` direttamente da GitHub (si aggiorna automaticamente ad ogni esecuzione) — apribile con Excel, Google Sheets, LibreOffice. Contiene già intestazioni colorate e colonne autodimensionate; se vuoi un grafico dell'equity nel tempo, seleziona i dati del foglio "Andamento" e inserisci un grafico a linee su "Equity totale (USD)".

### Limitazioni da conoscere

- **GitHub disattiva automaticamente i workflow schedulati dopo 60 giorni senza commit manuali nel repository.** Se il bot smette di girare dopo circa 2 mesi, vai su Actions → bot.yml → "Enable workflow" per riattivarlo (oppure fai un piccolo commit manuale ogni tanto).
- Gli orari del cron di GitHub Actions **non sono garantiti al minuto esatto** — nei momenti di alto carico sulla piattaforma può slittare di qualche minuto. Per questa strategia (che opera su timeframe di giorni) non è un problema.
- Ogni esecuzione crea un commit nel repository: dopo mesi di utilizzo la cronologia Git crescerà. Se ti infastidisce, puoi periodicamente "squashare" la storia — non influisce sul funzionamento del bot.
- Se anche Kraken dovesse diventare non raggiungibile da GitHub Actions in futuro, il modulo da modificare è solo `bot/data_feed.py` — la logica della strategia non dipende dalla fonte dati specifica.

## Consigli per il periodo di test con fondi virtuali

- **Fai girare il bot per almeno 4-8 settimane** prima di considerare capitale reale — la strategia opera su timeframe di giorni/settimane (media di regime a 30 giorni), quindi ha bisogno di tempo per mostrare il suo comportamento su cicli di mercato reali.
- Tieni d'occhio `trades.xlsx`: ogni riga spiega il motivo dell'operazione (breakout, trailing stop, cambio di regime) — utile per capire se il comportamento corrisponde alle aspettative del backtest.
- È normale che il bot resti a lungo senza fare trade se il mercato è in regime "bear" (prezzo sotto la media di 1500 candele) — è protezione del capitale, non un malfunzionamento.

## Riprodurre il backtest storico

```bash
python backtest/run_backtest.py --csv path/al/tuo/eth_15m.csv
```

Puoi modificare i parametri via riga di comando per ri-testare (vedi `python backtest/run_backtest.py --help`).

## Struttura del progetto

```
eth-regime-bot/
├── .github/
│   └── workflows/
│       └── bot.yml         # esegue il bot ogni 15 min sui server GitHub
├── bot/
│   ├── config.py           # parametri strategia + capitale + modalità paper/live
│   ├── main.py             # entry point, loop principale
│   ├── strategy.py         # logica Regime-Adaptive Pyramid (valutazione live)
│   ├── paper_trader.py     # portafoglio virtuale con persistenza stato
│   ├── excel_log.py        # aggiorna trades.xlsx ad ogni trade/snapshot
│   ├── data_feed.py        # download prezzi reali (API pubblica Kraken)
│   ├── live_trader.py      # esecuzione reale on-chain (solo se PAPER_TRADING=False)
│   ├── history_store.py    # gestisce lo storico persistente price_history.csv
│   ├── price_history.csv   # seed iniziale (2000 candele) + storico accumulato
│   └── indicators.py       # ATR, Donchian, media di regime
├── backtest/
│   ├── engine_v2.py        # motore di backtest CORRETTO (usa questo)
│   ├── strategies_v2.py    # strategie corrette + benchmark di riferimento
│   ├── backtest_engine.py  # motore vecchio (con look-ahead bias, solo storico)
│   ├── strategies.py       # strategie vecchie (solo storico)
│   └── run_backtest.py     # script per ri-eseguire il backtest storico
├── tests/
│   └── test_strategy.py    # test automatici (dati sintetici, no rete richiesta)
├── requirements.txt
├── requirements-live.txt   # dipendenze aggiuntive solo per esecuzione on-chain
└── LICENSE
```

## Passare al live trading (dopo aver validato in paper trading)

Quando sei pronto, e SOLO dopo settimane di validazione soddisfacente:

1. Leggi attentamente i commenti di sicurezza in `bot/config.py`
2. Installa le dipendenze aggiuntive: `pip install -r requirements-live.txt`
3. Imposta `PAPER_TRADING = False` in `config.py`
4. Configura `RPC_URL` e `BOT_PRIVATE_KEY` **come variabili d'ambiente**, mai nel codice
5. Usa un wallet **dedicato**, separato dai tuoi asset principali, con solo il capitale che vuoi rischiare
6. Testa prima su una testnet (es. Arbitrum Sepolia) prima di mainnet
7. Implementa il calcolo dinamico dello slippage minimo (`amountOutMinimum`) tramite il contratto Quoter di Uniswap — non incluso nello scheletro base per motivi di sicurezza/complessità, va aggiunto e testato con attenzione

**Nota sui costi**: la strategia esegue relativamente pochi trade (134 nel backtest su 5 anni), il che la rende sostenibile anche con capitale piccolo (100€) su una Layer 2 come Arbitrum o Base, dove i costi di gas sono minimi. Su Ethereum mainnet, i costi di gas renderebbero probabilmente l'operatività antieconomica con capitale così ridotto.

## Disclaimer

Questo non è un consiglio finanziario. I risultati del backtest si basano su dati storici e sono stati ottenuti ottimizzando i parametri sugli stessi dati usati per validarli — un certo grado di overfitting è possibile e le performance future potrebbero differire, anche significativamente, da quelle storiche. Il codice è uno scheletro funzionale pensato per essere esteso e testato con cura, non un prodotto finito pronto per la produzione. Il trading di criptovalute comporta il rischio di perdita, anche totale, del capitale.
