# 001 — Dal mock al primo backtest onesto

**Priorità:** P0 (prima di ogni altra cosa)
**Scritto contro commit:** `a537770`
**Stato:** TODO

---

## Perché questo, e solo questo

Oggi il motore gira in **mock path**: Jesse non è installato, quindi `core_engine/mcp_executor.py:175` ritorna metriche finte invece di un backtest. Le metriche sono pure formule sui parametri di rischio:

- `mcp_executor.py:158` → `simulated_drawdown = -round(pos_sizing * sl * 100.0 * 3.0, 2)`
- `mcp_executor.py:159` → `simulated_sharpe = round((0.04 / sl) * 0.9, 2)`
- `mcp_executor.py:19-28` → `_mock_trade_returns()` fabbrica 40 trade finti, così il gate "30 trade reali" del validatore (`quant_validator.py`, `MIN_REAL_TRADES = 30`) viene **scavalcato** e la validazione passa lo stesso.

Risultato: ogni "PASSED" verde è aritmetica garantita, non mercato. Finché è così, **nessun numero del progetto significa nulla** e non si può decidere niente sul trading.

L'obiettivo di questo piano è ottenere **un singolo backtest vero**, misurato su candele reali. Non aggiungere feature. Non rendere "production-grade". Solo: spegnere la finzione.

Insight chiave (lente ponytail): il primo backtest onesto **non richiede di riparare questa pipeline**. Jesse è uno strumento completo con la sua UI. Il percorso più pigro che funziona è far girare la strategia dentro Jesse standalone, separatamente dal motore SQE. La pipeline SQE si aggancia *dopo*.

---

## Percorso A — Il minimo assoluto (consigliato per Francesco)

Non installare/configurare Postgres a mano. Jesse fornisce un Docker Compose ufficiale che impacchetta Postgres + Redis + Jesse insieme: un comando e c'è tutto.

### Step A1 — Installare Docker Desktop
- Scaricare e installare Docker Desktop per Windows: https://www.docker.com/products/docker-desktop/
- Avviarlo, attendere che dica "running".
- **Verifica:** in PowerShell `docker --version` stampa una versione.
- **Se fallisce / Docker non parte su questo PC (serve WSL2/virtualizzazione):** STOP, passa al Percorso B.

### Step A2 — Avviare Jesse con Docker
- Seguire la guida ufficiale Docker di Jesse: https://docs.jesse.trade/docs/getting-started/#using-docker
- In pratica: clonare il template `jesse-docker`, `docker compose up`, aprire `http://localhost:9000` nel browser.
- **Verifica:** la dashboard web di Jesse si apre nel browser.

### Step A3 — Importare candele reali
- Nella UI di Jesse, sezione **Import Candles**.
- Exchange: **Binance Perpetual** (coerente con `jesse_workspace/routes.py:5`; l'import storico non richiede API key).
- Simbolo: `BTC-USDT`, timeframe gestito da Jesse (importa 1m, aggrega a 4h).
- Periodo: ultimi **24 mesi**, date che finiscono **almeno 7 giorni fa** (mai date future — vedi nota date sotto).
- **Verifica:** l'import arriva al 100% senza errori "no candles".

### Step A4 — Caricare la strategia e fare il backtest
- Copiare il contenuto di `jesse_workspace/strategies/SovereignStrategy/` (i file `__init__.py` e `params.py`) nella cartella `strategies/` del progetto Jesse Docker.
- Configurare il route in Jesse: `Binance Perpetual`, `BTC-USDT`, `4h`, `SovereignStrategy`.
- Lanciare il backtest dalla UI sul periodo importato.
- **Verifica (questo è IL momento della verità):** Jesse produce un report con metriche **reali**. Confrontale con i numeri mock attuali in `payload_drop/validation_report.json`. Saranno diversi — probabilmente molto peggiori. *Quello* è il dato onesto.

---

## Percorso B — Fallback se Docker non è praticabile

Installazione nativa (più passi, più fragile su Windows):

1. `python -m venv venv && .\venv\Scripts\activate`
2. `pip install jesse` (Python 3.10–3.12 obbligatorio).
3. Installare **Postgres** e **Redis** localmente (o via Docker singoli container). Configurare le credenziali DB in `jesse_workspace/` (variabili `DB_*`).
4. `jesse import-candles 'Binance Perpetual' BTC-USDT '<start>' '<end>'`
5. `jesse run` per la UI, oppure usare la pipeline SQE (`python run_simulation.py`) — vedi Step C sotto.

Se sia A che B falliscono per ragioni d'ambiente: STOP e riporta il blocco preciso. Non improvvisare workaround.

---

## Step trasversali — da fare INSIEME al primo backtest reale (non prima)

Questi hanno senso solo nel momento in cui i numeri diventano veri. Sono fix piccoli; falli quando arrivi al backtest, non come pre-lavoro.

### Step T1 — Date di backtest reali (one-liner)
- `run_simulation.py:32` ha hardcoded `start_date="2026-01-01", end_date="2026-06-01"` (futuro → nessun dato).
- Sostituire con un periodo passato reale, es. `start_date="2023-01-01", end_date="2024-12-31"`.
- **Se vuoi una guardia invece di una data fissa:** una riga che rifiuta `end_date` oltre `oggi - 7 giorni`. Opzionale, non obbligatoria.

### Step T2 — Non farsi ingannare dal mock (mitigazione 2 righe, NON uno STRICT_MODE)
- Il deliverable B1 di GLM propone un intero sistema `STRICT_MODE`. È sovra-ingegnerizzato.
- Minimo che basta: in `mcp_executor.py`, quando si ritorna il path mock (es. riga 176-181), aggiungere `"is_mock": True` al dict ritornato, e propagarlo come banner/campo nel `validation_report.json`. Così qualunque report finto è etichettato come tale.
- `# ponytail: flag is_mock invece di un sistema di env-flag; aggiungi STRICT_MODE solo se il mock viene usato in CI dove deve fallire hard.`
- **Verifica:** un run senza Jesse produce un report con `is_mock: true` visibile.

### Step T3 — Bug sizing ATR×2 vs stop fisso (fix concettuale, poche righe)
- Nel codice generato (`jesse_workspace/strategies/SovereignStrategy/__init__.py`) e nel **template che lo genera** in `core_engine/developer_bridge.py`:
  - `_position_qty()` (riga ~99) dimensiona con `stop_distance = self.atr * 2`.
  - `go_long()` (riga ~114) piazza lo stop a `self.price * (1 - sl_value)` → **base diversa**.
- Fix minimo: rendere coerenti le due basi. O lo stop usa `ATR*2` (`stop_price = self.price - self.atr * 2`), o il sizing usa la stessa percentuale fissa dello stop. Una delle due, non entrambe le basi.
- **Importante:** il fix va nel **template del generatore** (`developer_bridge.py`), non solo nel file generato, altrimenti il prossimo run lo sovrascrive.
- Nota: GLM dice "rischio 3-4× più alto" — la *direzione* è sbagliata (su BTC volatile la posizione risulta troppo *piccola*), ma l'incoerenza da sistemare è reale.
- **Verifica:** rigenerare la strategia (`python run_simulation.py`) e controllare che sizing e stop usino la stessa base.

### Step T4 — Coerenza exchange (one-liner doc)
- `routes.py:5` usa `Binance Perpetual`; i `docs/` citano Bybit. Scegliere UNO.
- Più pigro: tenere Binance (già nel routes, import storico senza API key) e correggere i riferimenti a Bybit nei docs. Nessun cambio di codice.

---

## Step C — Agganciare la pipeline SQE al Jesse reale (SOLO dopo che A o B funziona)

Una volta che `jesse` è sul PATH e le candele sono nel DB, la pipeline SQE smette automaticamente di usare il mock: `mcp_executor.py:128` controlla `shutil.which("jesse")`. Quindi:

- `python run_simulation.py` (con le date corrette dello Step T1) ora dovrebbe shellare un `jesse backtest` vero.
- **Verifica:** lo stdout NON contiene "Mock execution"; il `validation_report.json` ha `is_mock: false` (o assente) e metriche diverse dalle formule.
- Se il verdetto reale è FAILED (probabile con la strategia RSI+SMA attuale): **è il risultato corretto**, non un bug. Significa che la strategia non ha edge — esattamente ciò che il mock nascondeva.

---

## La strategia v2 di GLM — perché NON ora

Tentazione: copiare subito `GLM SQE analisi/SovereignStrategy_v2.py`. Verdetto: **no, è spreco adesso.**

- Non è un "drop-in": il generatore AST (`developer_bridge.py`) non può produrla; andrebbe copiata a mano, scavalcando il cuore del progetto (il loop AI→codice).
- Ha difetti propri non rifiniti: `_htf_trend_up()` ritorna sempre `True` (conferma multi-timeframe **spenta**); `should_short` di fatto sempre attivo (costoso su crypto per il funding); ~9 filtri simultanei che rischiano di non tradare quasi mai (→ niente trade = niente da validare).
- Soprattutto: **il suo valore è ignoto finché non la backtesti su dati veri.** Copiarla prima di avere l'harness di backtest è ottimizzare alla cieca.

**Cosa farne:** tienila come *riferimento di design* (trend filter EMA200, pullback, regime detection, scale-out sono idee giuste). Valutala dopo, dentro Jesse, allo stesso modo della v1: un altro backtest onesto da confrontare. Se la batte sui dati reali, allora vale la pena.

---

## Done criteria (tutto il piano)

1. Jesse gira (UI o CLI) con candele reali `BTC-USDT 4h` importate nel DB.
2. Un backtest reale della `SovereignStrategy` attuale ha prodotto metriche **misurate**, confrontate coi numeri mock.
3. Le date future in `run_simulation.py` sono sostituite con un periodo passato.
4. (Se si tocca il codice) il bug sizing/stop è reso coerente nel template `developer_bridge.py`, e i report mock sono etichettati `is_mock`.

Quando questi quattro punti sono veri, il progetto è passato da "demo auto-confermante" a "backtest onesto" — e *solo allora* ha senso aprire il discorso strategia v2, gate statistici, e live.

---

## Escape hatches

- Docker non parte (no virtualizzazione/WSL2) → Percorso B.
- Anche l'installazione nativa fallisce (conflitti dipendenze, Postgres) → STOP, riporta l'errore esatto. Non inventare workaround: l'ambiente è il blocco, va risolto quello.
- Il backtest reale dà 0 trade → normale per una strategia troppo selettiva; riporta il dato, non forzare parametri per "far apparire" trade.
